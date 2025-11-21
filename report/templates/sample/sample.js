const AGENT_SECTION_SELECTOR = '.agent-section';
const EXPAND_ALL_BUTTON_ID = 'agent-sections-expand-all';
const COLLAPSE_ALL_BUTTON_ID = 'agent-sections-collapse-all';

/**
 * Toggles the open state of all agent sections in the document.
 * @param {boolean} open - Whether to open (true) or close (false) the sections.
 */
function toggleAgentSections(open) {
    document.querySelectorAll(AGENT_SECTION_SELECTOR).forEach(section => {
        const alpineData = Alpine.$data(section);
        if (alpineData) {
            alpineData.open = open;
        }
    });
}

/**
 * Copies text content from the provided element ID.
 * @param {string} elementId - The ID containing the text to copy.
 * @param {HTMLElement} button - The button that triggered the action.
 */
function copyTextFromElement(elementId, button) {
    const element = document.getElementById(elementId);
    if (!element) {
        console.error(`Element not found: ${elementId}`);
        return;
    }

    const text = element.textContent;

    navigator.clipboard.writeText(text).then(() => {
        if (!button) {
            return;
        }

        const pathElement = button.querySelector('svg path');
        if (!pathElement) {
            return;
        }

        const originalPath = pathElement.getAttribute('d');

        // Checkmark icon SVG
        pathElement.setAttribute('d', 'M5 13l4 4L19 7');
        setTimeout(() => {
            pathElement.setAttribute('d', originalPath);
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy text:', err);
        alert('Failed to copy text to clipboard');
    });
}

document.addEventListener('DOMContentLoaded', function () {
    if (typeof hljs !== 'undefined') {
        hljs.highlightAll();
    }

    const agentSectionsExpandAllButton = document.getElementById(EXPAND_ALL_BUTTON_ID);
    if (agentSectionsExpandAllButton) {
        agentSectionsExpandAllButton.addEventListener('click', () => toggleAgentSections(true));
    }

    const agentSectionsCollapseAllButton = document.getElementById(COLLAPSE_ALL_BUTTON_ID);
    if (agentSectionsCollapseAllButton) {
        agentSectionsCollapseAllButton.addEventListener('click', () => toggleAgentSections(false));
    }
});
