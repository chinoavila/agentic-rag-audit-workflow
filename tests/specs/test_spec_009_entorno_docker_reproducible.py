import json
import re
from pathlib import Path

import pytest
import yaml


@pytest.mark.spec_009
class TestEntornoDockerReproducible:
    """Spec-009: Entorno Docker Reproducible (.ai/specs/platform/spec-009-entorno-docker-reproducible.md)"""

    @staticmethod
    def _get_project_root() -> Path:
        """Encuentra la raíz del proyecto (donde está docker-compose.yml)."""
        test_file = Path(__file__).resolve()
        # tests/specs/test_spec_009_entorno_docker_reproducible.py → project_root
        project_root = test_file.parent.parent.parent
        return project_root

    def test_docker_compose_config_defines_named_volumes_for_persistence(self):
        """Parsea docker-compose.yml y confirma persistencia: sqlite_data como volumen nombrado,
        Chroma como bind mount a ./data/chroma (decisión deliberada, no un volumen nombrado -- ver
        docs/plans/plan-tool-execution-permission-modes.md sección 1: el borrado del índice debe ser
        siempre una acción explícita del usuario sobre esa carpeta)."""
        project_root = self._get_project_root()
        docker_compose_path = project_root / "docker-compose.yml"

        assert docker_compose_path.exists(), f"docker-compose.yml no encontrado en {project_root}"

        with open(docker_compose_path, "r") as f:
            compose = yaml.safe_load(f)

        # Verificar que existe la sección top-level 'volumes'
        assert "volumes" in compose, "docker-compose.yml debe tener sección 'volumes' top-level"
        volumes = compose["volumes"]

        # chroma_data ya NO es un volumen nombrado (migrado a bind mount, task 15 del plan)
        assert "chroma_data" not in volumes, (
            "chroma_data no debe ser un volumen nombrado -- el índice Chroma persiste vía bind "
            "mount a ./data/chroma"
        )
        assert "sqlite_data" in volumes, "Volumen nombrado 'sqlite_data' no encontrado"
        assert (
            volumes["sqlite_data"].get("driver") == "local"
        ), "sqlite_data debe usar driver: local"

        # Verificar que el servicio 'backend' monta el bind mount de Chroma y el volumen de sqlite
        assert "services" in compose, "docker-compose.yml debe tener sección 'services'"
        backend = compose["services"].get("backend", {})
        assert backend, "Servicio 'backend' no encontrado"

        backend_volumes = backend.get("volumes", [])
        assert len(backend_volumes) > 0, "backend debe tener volúmenes montados"

        # Buscar los montes específicos en la lista de volúmenes
        volume_mount_strings = [str(v) for v in backend_volumes]
        chroma_bind_mounted = any(
            v.startswith("./data/chroma:") or v.startswith("./data/chroma :") for v in volume_mount_strings
        )
        sqlite_mounted = any("sqlite_data" in v for v in volume_mount_strings)

        assert chroma_bind_mounted, "backend debe montar ./data/chroma:/data/chroma (bind mount)"
        assert sqlite_mounted, "backend debe montar sqlite_data:/data"

    def test_env_example_keys_match_required_env_keys(self):
        """Verifica que .env.example contenga las claves que docker-compose.yml y código requieren."""
        project_root = self._get_project_root()
        docker_compose_path = project_root / "docker-compose.yml"
        env_example_path = project_root / ".env.example"

        assert env_example_path.exists(), f".env.example no encontrado en {project_root}"

        # Parsear docker-compose.yml
        with open(docker_compose_path, "r") as f:
            compose = yaml.safe_load(f)

        # Extraer variables de entorno requeridas por docker-compose.yml
        required_env_vars = set()

        # Buscar referencias ${VAR} y variables configurables documentadas
        for service_name, service_config in compose.get("services", {}).items():
            env_section = service_config.get("environment", [])

            if isinstance(env_section, list):
                # Formato: ["KEY=value", "KEY=${VAR}", ...]
                for env_var in env_section:
                    if isinstance(env_var, str) and "=" in env_var:
                        key, val = env_var.split("=", 1)
                        # Buscar referencias ${VAR}
                        matches = re.findall(r"\$\{([A-Z_]+)\}", val)
                        required_env_vars.update(matches)
                        # Agregar variables configurables documentadas
                        if key in [
                            "CHROMA_PERSIST_DIR",
                            "AUDIT_DATABASE_URL",
                            "BACKEND_API_URL",
                        ]:
                            required_env_vars.add(key)
            elif isinstance(env_section, dict):
                # Formato: {KEY: value, KEY: ${VAR}, ...}
                for key, val in env_section.items():
                    val_str = str(val)
                    matches = re.findall(r"\$\{([A-Z_]+)\}", val_str)
                    required_env_vars.update(matches)
                    if key in [
                        "CHROMA_PERSIST_DIR",
                        "AUDIT_DATABASE_URL",
                        "BACKEND_API_URL",
                    ]:
                        required_env_vars.add(key)

        # Parsear .env.example
        env_example_keys = set()
        with open(env_example_path, "r") as f:
            for line in f:
                line = line.strip()
                # Ignorar comentarios y líneas vacías
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key = line.split("=", 1)[0].strip()
                    env_example_keys.add(key)

        # Verificar que GROQ_API_KEY está presente (es la única ${VAR} real en compose)
        assert (
            "GROQ_API_KEY" in required_env_vars
        ), "GROQ_API_KEY debe ser referenciada en docker-compose.yml"
        assert (
            "GROQ_API_KEY" in env_example_keys
        ), "GROQ_API_KEY debe estar en .env.example"

        # Verificar que todas las variables requeridas están en .env.example
        missing_in_example = required_env_vars - env_example_keys
        assert (
            not missing_in_example
        ), f"Variables faltantes en .env.example: {missing_in_example}"

    def test_services_define_healthchecks(self):
        """Verifica que backend y chainlit tengan healthchecks definidos."""
        project_root = self._get_project_root()
        docker_compose_path = project_root / "docker-compose.yml"

        with open(docker_compose_path, "r") as f:
            compose = yaml.safe_load(f)

        services = compose.get("services", {})

        # Verificar backend
        backend = services.get("backend", {})
        assert backend, "Servicio 'backend' no encontrado"
        assert "healthcheck" in backend, "backend debe tener un healthcheck definido"
        assert backend["healthcheck"], "backend healthcheck no debe estar vacío"

        # Verificar chainlit
        chainlit = services.get("chainlit", {})
        assert chainlit, "Servicio 'chainlit' no encontrado"
        assert "healthcheck" in chainlit, "chainlit debe tener un healthcheck definido"
        assert chainlit["healthcheck"], "chainlit healthcheck no debe estar vacío"

    def test_docker_compose_down_v_is_blocked_by_guardrail(self):
        """Verifica que eliminacion de volumenes con flags peligrosos está bloqueada."""
        project_root = self._get_project_root()
        guardrail_path = project_root / ".ai" / "guardrails" / "restricted-ops.json"

        assert guardrail_path.exists(), f"guardrail file no encontrado en {guardrail_path}"

        with open(guardrail_path, "r") as f:
            guardrail = json.load(f)

        # Buscar en blocked_hard para entradas que protejan los volúmenes Chroma/DB
        blocked_hard = guardrail.get("blocked_hard", [])
        found = False
        for entry in blocked_hard:
            pattern = entry.get("pattern", "")
            reason = entry.get("reason", "")
            # Buscamos entradas que mencionen eliminar volúmenes de forma destructiva
            # (referenciadas en spec-009 acceptance criterion 2 y 3)
            if ("Chroma" in reason or "indice RAG" in reason or
                "audit trail" in reason or "volumen" in reason.lower()):
                found = True
                assert entry.get("alternative"), "Entrada debe tener 'alternative'"
                break

        assert (
            found
        ), "Debe existir entrada en blocked_hard para proteger volúmenes Chroma/DB"
