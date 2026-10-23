"""Lector IMAP de solo lectura (Fase 1 de FOLLOWUP_PLAN.md).

Conecta por IMAP SSL con contrasenas de aplicacion, busca correos incrementalmente
mediante UIDs (o 60 dias atras en la primera corrida) y normaliza remitente, dominio,
asunto, fecha, texto plano, adjuntos .ics y link web de Gmail sin marcar nada como leido.
"""
from datetime import datetime, timedelta, timezone
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime
import email
import imaplib
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple
import urllib.parse

import markdownify
import profile_paths

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def get_credentials() -> Dict[str, str]:
    """Obtiene las credenciales de correo desde profile_paths.resolve('.env') o entorno."""
    creds = {
        "MAIL_USER": os.environ.get("MAIL_USER", "").strip(),
        "MAIL_APP_PASSWORD": os.environ.get("MAIL_APP_PASSWORD", "").strip(),
        "MAIL_IMAP_HOST": os.environ.get("MAIL_IMAP_HOST", "").strip() or "imap.gmail.com",
        "MAIL_IMAP_PORT": os.environ.get("MAIL_IMAP_PORT", "993").strip(),
    }

    env_path = profile_paths.resolve(".env")
    if os.path.isfile(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k in creds and not creds[k]:
                        creds[k] = v
        except Exception:
            pass

    return creds


def has_credentials() -> bool:
    """Verifica si las credenciales minimas de correo estan configuradas."""
    creds = get_credentials()
    return bool(creds.get("MAIL_USER") and creds.get("MAIL_APP_PASSWORD"))


def get_state_file_path() -> str:
    """Ruta al archivo donde se persiste el ultimo UID procesado."""
    return profile_paths.resolve("mail_state.json")


def load_mail_state() -> Dict[str, Any]:
    """Carga el estado de UIDs por cuenta."""
    path = get_state_file_path()
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_mail_state(state: Dict[str, Any]):
    """Guarda el estado de UIDs."""
    path = get_state_file_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[WARN] No se pudo guardar mail_state.json: {e}")


def decode_mime_header(header_val: Optional[str]) -> str:
    """Decodifica un encabezado MIME a texto legible UTF-8."""
    if not header_val:
        return ""
    try:
        parts = decode_header(header_val)
        decoded = []
        for content, encoding in parts:
            if isinstance(content, bytes):
                enc = encoding or "utf-8"
                try:
                    decoded.append(content.decode(enc, errors="replace"))
                except LookupError:
                    decoded.append(content.decode("utf-8", errors="replace"))
            else:
                decoded.append(str(content))
        return " ".join(decoded).strip()
    except Exception:
        return str(header_val)


def parse_ics(ics_text: str) -> Dict[str, Optional[str]]:
    """Extrae DTSTART, SUMMARY y URL de un archivo o contenido .ics sin dependencias externas."""
    out = {"dtstart": None, "summary": None, "url": None}
    if not ics_text:
        return out

    for line in ics_text.splitlines():
        line = line.strip()
        if line.startswith("DTSTART"):
            parts = line.split(":", 1)
            if len(parts) == 2:
                out["dtstart"] = parts[1].strip()
        elif line.startswith("SUMMARY:"):
            out["summary"] = line[len("SUMMARY:"):].strip()
        elif line.startswith("URL:"):
            out["url"] = line[len("URL:"):].strip()
        elif line.startswith("DESCRIPTION:") and not out["url"]:
            m = re.search(r"https?://\S+", line)
            if m:
                out["url"] = m.group(0).rstrip(")>\"'")

    return out


def parse_email_message(raw_bytes: bytes, uid: Optional[int] = None, gm_msgid: Optional[str] = None) -> Dict[str, Any]:
    """Parsea los bytes de un correo RFC 822 y devuelve un diccionario normalizado."""
    msg = email.message_from_bytes(raw_bytes)

    # 1. Remitente y dominios
    from_header = decode_mime_header(msg.get("From", ""))
    sender_name, sender_email = parseaddr(from_header)
    sender_email = sender_email.strip().lower()
    sender_domain = sender_email.split("@")[1] if "@" in sender_email else ""

    reply_to_header = decode_mime_header(msg.get("Reply-To", ""))
    _, reply_to_email = parseaddr(reply_to_header)
    reply_to_email = reply_to_email.strip().lower()
    reply_to_domain = reply_to_email.split("@")[1] if "@" in reply_to_email else ""

    # 2. Asunto
    subject = decode_mime_header(msg.get("Subject", ""))

    # 3. Message-ID
    raw_msg_id = msg.get("Message-ID", "")
    message_id = raw_msg_id.strip().strip("<>")
    if not message_id:
        # Fallback determinista
        message_id = f"gen-{uid or 0}-{abs(hash((subject, sender_email)))}"

    # 4. Fecha de recepcion
    date_header = msg.get("Date")
    received_at = None
    if date_header:
        try:
            dt = parsedate_to_datetime(date_header)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            received_at = dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            received_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    else:
        received_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    # 5. Cuerpos texto plano, HTML y adjuntos .ics
    body_text_parts: List[str] = []
    html_parts: List[str] = []
    ics_data: Dict[str, Optional[str]] = {"dtstart": None, "summary": None, "url": None}

    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            cdisp = str(part.get("Content-Disposition", "")).lower()
            fname = part.get_filename() or ""

            # Detectar .ics
            if ctype == "text/calendar" or fname.endswith(".ics"):
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        ics_text = payload.decode("utf-8", errors="replace")
                        ics_data = parse_ics(ics_text)
                except Exception:
                    pass

            if "attachment" in cdisp and not fname.endswith(".ics"):
                continue

            payload = part.get_payload(decode=True)
            if not payload:
                continue

            charset = part.get_content_charset() or "utf-8"
            try:
                decoded_str = payload.decode(charset, errors="replace")
            except LookupError:
                decoded_str = payload.decode("utf-8", errors="replace")

            if ctype == "text/plain":
                body_text_parts.append(decoded_str)
            elif ctype == "text/html":
                html_parts.append(decoded_str)
    else:
        ctype = msg.get_content_type()
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            try:
                decoded_str = payload.decode(charset, errors="replace")
            except LookupError:
                decoded_str = payload.decode("utf-8", errors="replace")

            if ctype == "text/plain":
                body_text_parts.append(decoded_str)
            elif ctype == "text/html":
                html_parts.append(decoded_str)

    html_body = "\n".join(html_parts)
    if body_text_parts:
        body_text = "\n".join(body_text_parts)
    elif html_parts:
        try:
            body_text = markdownify.markdownify(html_body)
        except Exception:
            body_text = re.sub(r"<[^>]+>", " ", html_body)
    else:
        body_text = ""

    # Normalizar espacios
    body_text = re.sub(r"\r\n|\r", "\n", body_text).strip()

    # 6. Link web al correo en Gmail
    web_link = ""
    if gm_msgid:
        try:
            msgid_int = int(gm_msgid)
            hex_id = hex(msgid_int)[2:]
            web_link = f"https://mail.google.com/mail/u/0/#all/{hex_id}"
        except Exception:
            web_link = f"https://mail.google.com/mail/u/0/#search/rfc822msgid%3A{urllib.parse.quote(message_id)}"
    elif message_id:
        web_link = f"https://mail.google.com/mail/u/0/#search/rfc822msgid%3A{urllib.parse.quote(message_id)}"

    return {
        "uid": uid,
        "gm_msgid": gm_msgid,
        "message_id": message_id,
        "sender": from_header,
        "sender_name": sender_name,
        "sender_email": sender_email,
        "sender_domain": sender_domain,
        "reply_to": reply_to_header,
        "reply_to_email": reply_to_email,
        "reply_to_domain": reply_to_domain,
        "subject": subject,
        "received_at": received_at,
        "body_text": body_text,
        "html_body": html_body,
        "ics_data": ics_data,
        "link": web_link,
    }


def connect_imap(creds: Dict[str, str]) -> imaplib.IMAP4_SSL:
    """Conecta al servidor IMAP por SSL y realiza el login."""
    host = creds.get("MAIL_IMAP_HOST") or "imap.gmail.com"
    port = int(creds.get("MAIL_IMAP_PORT") or 993)
    user = creds.get("MAIL_USER", "")
    password = creds.get("MAIL_APP_PASSWORD", "")

    client = imaplib.IMAP4_SSL(host, port)
    client.login(user, password)
    return client


def select_mailbox(client: imaplib.IMAP4_SSL, is_gmail: bool = True) -> str:
    """Selecciona el buzon en modo solo lectura (readonly=True)."""
    if is_gmail:
        # Intentar [Gmail]/All Mail o [Gmail]/Todos
        for folder in ['"[Gmail]/All Mail"', '"[Gmail]/Todos"', "INBOX"]:
            status, _ = client.select(folder, readonly=True)
            if status == "OK":
                return folder
        status, _ = client.select("INBOX", readonly=True)
        return "INBOX"
    else:
        status, _ = client.select("INBOX", readonly=True)
        return "INBOX"


def fetch_emails(creds: Optional[Dict[str, str]] = None,
                 custom_gm_raw: Optional[str] = None,
                 lookback_days: int = 60,
                 max_emails: int = 150) -> List[Dict[str, Any]]:
    """Lee correos nuevos desde la cuenta IMAP sin marcarlos como leidos.
    
    Usa readonly=True y BODY.PEEK[].
    Si hay last_uid, busca incrementalmente (UID {last_uid + 1}:*).
    Si no hay last_uid (primera corrida), busca hasta lookback_days atras.
    """
    if creds is None:
        creds = get_credentials()

    if not creds.get("MAIL_USER") or not creds.get("MAIL_APP_PASSWORD"):
        return []

    account = creds["MAIL_USER"]
    is_gmail = "gmail.com" in (creds.get("MAIL_IMAP_HOST") or "").lower() or account.endswith("@gmail.com")

    client = None
    try:
        client = connect_imap(creds)
    except Exception as e:
        print(f"[ERROR] Error al conectar a IMAP ({account}): {e}")
        return []

    try:
        select_mailbox(client, is_gmail=is_gmail)
        state = load_mail_state()
        acct_state = state.get(account, {})
        last_uid = acct_state.get("last_uid")

        uids: List[int] = []

        if last_uid:
            search_crit = f"UID {last_uid + 1}:*"
            status, data = client.uid("search", None, search_crit)
            if status == "OK" and data and data[0]:
                uids = [int(u) for u in data[0].split() if int(u) > last_uid]
        else:
            # Primera corrida: mirar lookback_days atras
            since_date = datetime.now(timezone.utc) - timedelta(days=lookback_days)
            date_str = since_date.strftime("%d-%b-%Y")

            if is_gmail:
                # Sintaxis Gmail X-GM-RAW
                raw_query = f'after:{since_date.strftime("%Y/%m/%d")}'
                if custom_gm_raw:
                    raw_query = f"{raw_query} {custom_gm_raw}"
                status, data = client.uid("search", None, "X-GM-RAW", f'"{raw_query}"')
                if status == "OK" and data and data[0]:
                    uids = [int(u) for u in data[0].split()]
                else:
                    # Fallback a SINCE estandar
                    status, data = client.uid("search", None, f'(SINCE "{date_str}")')
                    if status == "OK" and data and data[0]:
                        uids = [int(u) for u in data[0].split()]
            else:
                status, data = client.uid("search", None, f'(SINCE "{date_str}")')
                if status == "OK" and data and data[0]:
                    uids = [int(u) for u in data[0].split()]

        uids.sort()
        if max_emails and len(uids) > max_emails:
            uids = uids[-max_emails:]

        results: List[Dict[str, Any]] = []
        highest_uid = last_uid or 0

        for uid in uids:
            highest_uid = max(highest_uid, uid)
            fetch_cmd = "(BODY.PEEK[] X-GM-MSGID)" if is_gmail else "(BODY.PEEK[])"
            status, fetch_data = client.uid("fetch", str(uid), fetch_cmd)
            if status != "OK" or not fetch_data:
                continue

            raw_bytes = None
            gm_msgid = None

            for item in fetch_data:
                if isinstance(item, tuple):
                    raw_bytes = item[1]
                    header_line = item[0].decode("utf-8", errors="ignore") if isinstance(item[0], bytes) else str(item[0])
                    m = re.search(r"X-GM-MSGID\s+(\d+)", header_line)
                    if m:
                        gm_msgid = m.group(1)
                elif isinstance(item, bytes):
                    m = re.search(r"X-GM-MSGID\s+(\d+)", item.decode("utf-8", errors="ignore"))
                    if m:
                        gm_msgid = m.group(1)

            if raw_bytes:
                parsed = parse_email_message(raw_bytes, uid=uid, gm_msgid=gm_msgid)
                results.append(parsed)

        # Actualizar estado si vimos UIDs nuevos
        if highest_uid > (last_uid or 0):
            acct_state["last_uid"] = highest_uid
            acct_state["last_check"] = datetime.now(timezone.utc).isoformat()
            state[account] = acct_state
            save_mail_state(state)

        return results

    except Exception as e:
        print(f"[ERROR] Error durante lectura IMAP: {e}")
        return []
    finally:
        try:
            client.close()
        except Exception:
            pass
        try:
            client.logout()
        except Exception:
            pass


if __name__ == "__main__":
    if not has_credentials():
        print("[INFO] Credenciales de correo no configuradas (MAIL_USER / MAIL_APP_PASSWORD en .env). Saliendo.")
        sys.exit(0)

    print("[INFO] Conectando a correo para lectura...")
    emails = fetch_emails(max_emails=10)
    print(f"[INFO] Correos obtenidos: {len(emails)}")
    for em in emails:
        print(f" - [{em['received_at']}] {em['sender_name']} <{em['sender_email']}>: {em['subject']}")
