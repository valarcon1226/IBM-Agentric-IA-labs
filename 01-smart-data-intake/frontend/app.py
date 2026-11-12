import os
from typing import Any, Literal
from uuid import UUID

import httpx

ReviewAction = Literal["approve", "reject"]
DATA_FIELDS = ("first_name", "last_name", "email", "phone", "company")
FIELD_LABELS = {
    "first_name": "Nombre",
    "last_name": "Apellido",
    "email": "Email",
    "phone": "Teléfono",
    "company": "Empresa",
}


def review_endpoint(api_url: str, upload_id: str) -> str:
    try:
        normalized_upload_id = UUID(upload_id)
    except ValueError:
        raise ValueError("El upload_id debe ser un UUID válido.") from None
    return f"{api_url.rstrip('/')}/api/v1/intake/{normalized_upload_id}/review"


def get_pending_reviews(
    client: httpx.Client, api_url: str, api_key: str, upload_id: str
) -> list[dict[str, Any]]:
    response = client.get(
        review_endpoint(api_url, upload_id),
        headers={"Authorization": f"Bearer {api_key}"},
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("pending_reviews"), list):
        raise ValueError("La API devolvió una respuesta de revisión no válida.")
    reviews = payload["pending_reviews"]
    if not all(isinstance(item, dict) for item in reviews):
        raise ValueError("La API devolvió una fila de revisión no válida.")
    return reviews


def submit_review(
    client: httpx.Client,
    api_url: str,
    api_key: str,
    upload_id: str,
    record_id: str,
    action: ReviewAction,
    corrected_data: dict[str, str] | None = None,
) -> None:
    payload: dict[str, Any] = {"record_id": record_id, "action": action}
    if action == "approve" and corrected_data is not None:
        payload["corrected_data"] = corrected_data
    response = client.post(
        review_endpoint(api_url, upload_id),
        headers={"Authorization": f"Bearer {api_key}"},
        json=payload,
    )
    response.raise_for_status()


def show_api_error(st: Any, error: Exception) -> None:
    if isinstance(error, httpx.HTTPStatusError):
        status_code = error.response.status_code
        if status_code == 401:
            message = "La API rechazó la API key (401). Revisa la configuración."
        elif status_code == 404:
            message = "No se encontró el upload o la fila de revisión (404)."
        else:
            message = f"La API devolvió un error HTTP {status_code}."
    elif isinstance(error, (httpx.RequestError, httpx.InvalidURL)):
        message = "No se pudo conectar con la API. Revisa API_URL y que el backend esté disponible."
    else:
        message = str(error)
    st.error(message)


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="Revisión de datos", layout="wide")
    st.title("Revisión de datos")
    api_url = os.getenv("API_URL", "").strip()
    api_key = os.getenv("API_KEY", "")
    if not api_url or not api_key:
        st.error("Configura API_URL y API_KEY en las variables de entorno.")
        return

    upload_id = st.text_input("Upload ID").strip()
    if not upload_id:
        st.info("Introduce un upload_id para consultar las filas pendientes.")
        return

    try:
        with httpx.Client(timeout=10) as client:
            reviews = get_pending_reviews(client, api_url, api_key, upload_id)
            if not reviews:
                st.info("No hay filas pendientes de revisión para este upload.")
                return

            for item in reviews:
                record_id = str(item["record_id"])
                data = item["data"]
                with st.container(border=True):
                    st.subheader(f"Fila {item['line_number']}")
                    st.write("Datos recibidos")
                    st.json(data)
                    st.write("Motivos", item["reasons"])
                    with st.form(f"review-{record_id}"):
                        edited_data = {
                            field: st.text_input(
                                FIELD_LABELS[field],
                                value=str(data.get(field, "")),
                                key=f"{record_id}-{field}",
                            )
                            for field in DATA_FIELDS
                        }
                        approve_column, reject_column = st.columns(2)
                        with approve_column:
                            approve = st.form_submit_button("Aprobar", type="primary")
                        with reject_column:
                            reject = st.form_submit_button("Rechazar")

                        original_data = {field: str(data.get(field, "")) for field in DATA_FIELDS}
                        if approve:
                            corrected_data = edited_data if edited_data != original_data else None
                            submit_review(
                                client,
                                api_url,
                                api_key,
                                upload_id,
                                record_id,
                                "approve",
                                corrected_data,
                            )
                            st.rerun()
                        if reject:
                            submit_review(client, api_url, api_key, upload_id, record_id, "reject")
                            st.rerun()
    except (httpx.HTTPStatusError, httpx.RequestError, httpx.InvalidURL, ValueError) as error:
        show_api_error(st, error)


if __name__ == "__main__":
    main()
