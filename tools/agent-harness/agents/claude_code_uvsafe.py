"""ClaudeCode agent variant that pre-installs uv for verifier resilience.

TB2 verifiers download uv from github releases at test time; intermittent
container TCP failures to github.com made otherwise-passing solutions
score 0 (fix-ocaml-gc in iter05-runF, log-summary-date-ranges in
iter06-runG, and others). The verifier's test.sh tolerates its own
download failing when uv/uvx are already present, so installing uv
during the agent phase (retried, best-effort) removes the failure class
without touching tasks, verifiers, or scoring.

Wire-up (see bench/run_subset.sh): PYTHONPATH=<harness/agents> harbor
run --agent-import-path claude_code_uvsafe:ClaudeCodeUvSafe ...
"""

from harbor.agents.installed.claude_code import ClaudeCode

_UV_PREINSTALL = (
    "for i in 1 2 3; do "
    "  command -v uvx >/dev/null 2>&1 && break; "
    "  curl -fsSL https://astral.sh/uv/install.sh | sh && break; "
    "  sleep 10; "
    "done; "
    "command -v uvx >/dev/null 2>&1 || "
    "  ls $HOME/.local/bin/uvx >/dev/null 2>&1 || "
    "  echo 'uv pre-install failed (best-effort, continuing)'; "
    "true"
)


class ClaudeCodeUvSafe(ClaudeCode):
    @staticmethod
    def name() -> str:
        return "claude-code-uvsafe"

    async def setup(self, environment) -> None:
        await super().setup(environment)
        # Best-effort; must never fail the trial itself.
        try:
            await environment.exec(
                command=_UV_PREINSTALL, user="root", timeout_sec=180
            )
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("uv pre-install skipped: %s", exc)
