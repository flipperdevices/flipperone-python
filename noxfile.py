"""The checks CI runs, locally: ``uvx nox`` (all), ``uvx nox -s tests-3.12`` (one)."""

import nox

nox.options.default_venv_backend = "uv"
PYTHONS = ["3.12", "3.13", "3.14"]


@nox.session(python=PYTHONS)
def tests(session: nox.Session) -> None:
    session.install("-e", ".[ssh]", "pytest")
    session.run("pytest", *session.posargs)


@nox.session(python=PYTHONS[0])
def lint(session: nox.Session) -> None:
    session.install("-e", ".[ssh]", "ruff", "mypy", "types-paramiko", "types-pyserial")
    session.run("ruff", "check", "src", "tests", "examples", "noxfile.py")
    session.run("mypy")
