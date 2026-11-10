"""Tools shared by both engines: corpus search and a safe calculator."""

import ast
import operator
import re
from pathlib import Path

CORPUS_DIR = Path(__file__).resolve().parent.parent / "corpus"
_WORD = re.compile(r"\w{3,}")


def search_corpus(query: str, sources: set[str] | None = None) -> str:
    """Return the 3 corpus documents that share the most words with the query.

    `sources` collects the file names returned, so the report can cite them.
    """
    words = {w.lower() for w in _WORD.findall(query)}
    scored = []
    for path in sorted(CORPUS_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        score = len(words & {w.lower() for w in _WORD.findall(text)})
        if score:
            scored.append((score, path.name, text))
    if not scored:
        return "No documents matched the query."
    scored.sort(key=lambda s: -s[0])
    top = scored[:3]
    if sources is not None:
        sources.update(name for _, name, _ in top)
    return "\n\n".join(f"[{name}]\n{text.strip()}" for _, name, text in top)


_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def calculate(expression: str) -> str:
    """Evaluate + - * / and parentheses only (no power, names or calls). Max 60 characters."""
    if len(expression) > 60:
        return "Error: expression too long (max 60 characters)."

    def ev(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.operand))
        raise ValueError("only numbers and + - * / ( ) are allowed")

    try:
        result = ev(ast.parse(expression, mode="eval").body)
    except (SyntaxError, ValueError, ZeroDivisionError) as e:
        return f"Error: {e}"
    return str(round(result, 4))
