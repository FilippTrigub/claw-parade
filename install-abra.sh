#!/bin/bash
set -e
AGENT_NAME="abra"
AGENT_DISPLAY_NAME="Abra"
REPO_URL="${REPO_URL:-https://github.com/FilippTrigub/claw-parade.git}"
REPO_BRANCH="${REPO_BRANCH:-main}"
HOST_OPENCLAW_DIR="${HOME}/.openclaw"
CONTAINER_OPENCLAW_DIR="/home/node/.openclaw"
AGENT_WORKSPACE_HOST="${HOST_OPENCLAW_DIR}/workspace-${AGENT_NAME}"
AGENT_WORKSPACE_CONTAINER="${CONTAINER_OPENCLAW_DIR}/workspace-${AGENT_NAME}"
SKILLS_DEST="${AGENT_WORKSPACE_HOST}/skills"

echo "Installing Abra - Agent de Branding..."
echo

command -v jq >/dev/null 2>&1 || { echo "jq required: brew install jq"; exit 1; }

if [ ! -d "${HOST_OPENCLAW_DIR}/agents/${AGENT_NAME}" ]; then
    openclaw agents add "${AGENT_NAME}" 2>/dev/null || true
fi

mkdir -p "${AGENT_WORKSPACE_HOST}"
cat > "${AGENT_WORKSPACE_HOST}/SOUL.md" << 'SOUL'
# Abra - Agent de Branding
## Role
Personal Brand Content Agent for managing and growing personal brands.
## Capabilities
Brand identity management, branded content generation, image/video processing, content scheduling, brand asset management.
## Skills
persona, verbatim, snip, cutlab, render, liven, keyer, tween, score, demix, alt, knockout, portrait, grade, filter, mux, buffer, canva
SOUL

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}"
SKILL_SOURCE="${REPO_ROOT}/skills"

if [ ! -d "${SKILL_SOURCE}" ]; then
    TEMP_CLONE=$(mktemp -d)
    git clone --depth 1 -b "${REPO_BRANCH}" "${REPO_URL}" "${TEMP_CLONE}"
    SKILL_SOURCE="${TEMP_CLONE}/skills"
fi

mkdir -p "${SKILLS_DEST}"
for skill_dir in "${SKILL_SOURCE}"/*; do
    [ -d "${skill_dir}" ] || continue
    skill_name=$(basename "${skill_dir}")
    [[ "${skill_name}" == "input" || "${skill_name}" == "output" || "${skill_name}" == ".venv" ]] && continue
    rm -rf "${SKILLS_DEST}/${skill_name}"
    cp -r "${skill_dir}" "${SKILLS_DEST}/${skill_name}"
    echo "  + ${skill_name}"
done
[ -n "${TEMP_CLONE}" ] && rm -rf "${TEMP_CLONE}"

CONFIG_FILE="${HOST_OPENCLAW_DIR}/openclaw.json"
cp "${CONFIG_FILE}" "${CONFIG_FILE}.backup.$(date +%Y%m%d%H%M%S)"

jq '.agents //= {"list": []}' "${CONFIG_FILE}" > "${CONFIG_FILE}.tmp" && mv "${CONFIG_FILE}.tmp" "${CONFIG_FILE}"

if ! jq -e ".agents.list[] | select(.id == \"${AGENT_NAME}\")" "${CONFIG_FILE}" >/dev/null 2>&1; then
    AGENT_JSON=$(jq -n --arg id "${AGENT_NAME}" --arg name "${AGENT_DISPLAY_NAME}" --arg ws "${AGENT_WORKSPACE_CONTAINER}" '{id: $id, name: $name, workspace: $ws}')
    jq ".agents.list += [${AGENT_JSON}]" "${CONFIG_FILE}" > "${CONFIG_FILE}.tmp" && mv "${CONFIG_FILE}.tmp" "${CONFIG_FILE}"
fi

if ! jq ".bindings[]? | select(.agentId == \"${AGENT_NAME}\")" "${CONFIG_FILE}" 2>/dev/null | grep -q .; then
    jq '.bindings //= []' "${CONFIG_FILE}" > "${CONFIG_FILE}.tmp" && mv "${CONFIG_FILE}.tmp" "${CONFIG_FILE}"
    BINDING_JSON=$(jq -n --arg a "${AGENT_NAME}" --arg c "telegram" '{agentId: $a, match: {channel: $c}}')
    jq ".bindings += [${BINDING_JSON}]" "${CONFIG_FILE}" > "${CONFIG_FILE}.tmp" && mv "${CONFIG_FILE}.tmp" "${CONFIG_FILE}"
fi

openclaw gateway restart 2>/dev/null || true

echo
echo "Done! Agent '${AGENT_DISPLAY_NAME}' installed."
echo "Workspace: ${AGENT_WORKSPACE_HOST}"
echo "Skills: ${SKILLS_DEST}"
echo
echo "To customize, edit: ${CONFIG_FILE}"
echo "Restart gateway: openclaw gateway restart"
