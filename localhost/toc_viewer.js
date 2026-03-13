import { initializeDirectory } from './directory.js';

document.addEventListener('DOMContentLoaded', async () => {
    const tocPane = document.getElementById('toc-pane');
    const tocContent = document.getElementById('toc-content');
    const pinButton = document.getElementById('toc-pin-button');
    const resizeHandle = document.getElementById('toc-resize-handle');
    const leftPane = document.getElementById('left-pane');
    const leftPaneResizeHandle = document.getElementById('left-pane-resize-handle');

    if (!tocPane || !tocContent) return;

    // --- Redirection Logic (Index Page Only) ---
    // Try to open the last visited transcript, or fallback to the first available one.
    // We check for trailing slashes or explicit index.html
    const isIndexPage = window.location.pathname.endsWith('index.html') || window.location.pathname === '/' || window.location.pathname.endsWith('/');

    if (!isIndexPage) {
        // We are on a transcript page. Save this as the last opened state.
        localStorage.setItem('lastOpenedTranscript', window.location.pathname);
    }

    // --- Initialization ---
    // Wrap header and content in a container for flyout behavior
    let tocWrapper = document.getElementById('toc-wrapper');
    if (!tocWrapper) {
        tocWrapper = document.createElement('div');
        tocWrapper.id = 'toc-wrapper';
        // Move header and content into wrapper
        const header = document.getElementById('toc-header');
        const content = document.getElementById('toc-content');
        if (header) tocWrapper.appendChild(header);
        if (content) tocWrapper.appendChild(content);

        // Insert wrapper into pane (resize handle stays outside)
        tocPane.insertBefore(tocWrapper, resizeHandle);
    }

    // Initialize directory
    // We await this so we can perform post-render actions (like fallback redirect)
    await initializeDirectory(document.getElementById('toc-content'), {
        activePath: window.location.pathname, // Highlights current page
        linkHrefGenerator: (path) => path
    });

    // --- Redirection Logic (Index Page Only) ---
    if (isIndexPage) {
        const urlParams = new URLSearchParams(window.location.search);
        if (!urlParams.has('no_redirect')) {
            let targetUrl = null;
            const lastOpened = localStorage.getItem('lastOpenedTranscript');

            if (lastOpened && lastOpened !== 'null') {
                try {
                    // Check if it exists
                    const response = await fetch(lastOpened, { method: 'HEAD' });
                    if (response.ok) {
                        targetUrl = lastOpened;
                    } else {
                        console.warn("Last opened transcript not found (404/Error):", lastOpened);
                    }
                } catch (e) {
                    console.warn("Error checking last opened transcript:", e);
                }
            }

            // If no valid lastOpened, fallback to first item
            if (!targetUrl) {
                const firstLink = document.querySelector('#toc-content a.toc-link');
                if (firstLink) {
                    targetUrl = firstLink.href;
                }
            }

            // Perform Redirect
            if (targetUrl) {
                window.location.href = targetUrl;
                return;
            }
        }
    }

    // --- Pinning Logic ---
    let savedState = null;
    try {
        savedState = localStorage.getItem('tocPinned');
    } catch (e) {
        console.warn('localStorage not accessible:', e);
    }
    let isPinned = savedState === null ? true : savedState === 'true';

    // Force pinned on index page (though we redirect usually, but if no_redirect used)
    if (isIndexPage) {
        isPinned = true;
    }

    function updatePinState() {
        if (isPinned) {
            tocPane.classList.add('pinned');
            tocPane.classList.remove('unpinned');
            tocPane.classList.remove('expanded'); // Ensure it's not in expanded state
            if (pinButton) {
                pinButton.textContent = '📌'; // Pinned icon
                pinButton.title = "Unpin ToC";
            }
        } else {
            tocPane.classList.remove('pinned');
            tocPane.classList.add('unpinned');
            if (pinButton) {
                pinButton.textContent = '📍'; // Unpinned icon
                pinButton.title = "Pin ToC";
            }
        }

        // Only save state if NOT on index page
        if (!isIndexPage) {
            try {
                localStorage.setItem('tocPinned', isPinned);
            } catch (e) {
                // Ignore write errors
            }
        }
    }

    if (pinButton) {
        if (isIndexPage) {
            pinButton.style.display = 'none';
        }

        pinButton.addEventListener('click', (e) => {
            e.stopPropagation(); // Prevent bubbling
            isPinned = !isPinned;
            updatePinState();
        });
    }

    // Outlook-like behavior:
    // When unpinned, clicking the hamburger (or the strip) toggles "expanded" mode (overlay).
    tocPane.addEventListener('click', (e) => {
        if (tocPane.classList.contains('unpinned')) {
            // If clicking the pin button, don't toggle expand (handled above)
            if (e.target === pinButton) return;

            // Toggle expanded state
            tocPane.classList.toggle('expanded');
        }
    });

    // Close expanded pane when clicking outside
    document.addEventListener('click', (e) => {
        if (tocPane.classList.contains('unpinned') && tocPane.classList.contains('expanded')) {
            if (!tocPane.contains(e.target)) {
                tocPane.classList.remove('expanded');
            }
        }
    });

    // Initial state
    updatePinState();

    // --- Resizing Logic ---
    let isResizing = false;
    let isLeftResizing = false;

    if (resizeHandle) {
        resizeHandle.addEventListener('mousedown', (e) => {
            isResizing = true;
            document.body.style.cursor = 'ew-resize';
            document.body.classList.add('no-select'); // Prevent text selection while dragging
            e.stopPropagation();
        });
    }

    if (leftPaneResizeHandle) {
        leftPaneResizeHandle.addEventListener('mousedown', (e) => {
            isLeftResizing = true;
            document.body.style.cursor = 'ew-resize';
            document.body.classList.add('no-select');
            e.stopPropagation();
        });
    }

    document.addEventListener('mousemove', (e) => {
        if (isResizing) {
            // Calculate new width
            let newWidth = e.clientX;
            if (newWidth < 200) newWidth = 200;
            if (newWidth > 600) newWidth = 600;
            tocPane.style.width = `${newWidth}px`;
        }
        if (isLeftResizing && leftPane) {
            const container = document.getElementById('content-container');
            const containerLeft = container ? container.getBoundingClientRect().left : 0;
            const tocWidth = tocPane ? tocPane.getBoundingClientRect().width : 0;
            let newWidth = e.clientX - containerLeft - tocWidth;
            if (newWidth < 200) newWidth = 200;
            if (newWidth > window.innerWidth * 0.7) newWidth = window.innerWidth * 0.7;
            leftPane.style.width = `${newWidth}px`;
        }
    });

    document.addEventListener('mouseup', () => {
        if (isResizing) {
            isResizing = false;
            document.body.style.cursor = '';
            document.body.classList.remove('no-select');
            try {
                localStorage.setItem('tocWidth', tocPane.style.width);
            } catch (e) {
                // Ignore
            }
        }
        if (isLeftResizing) {
            isLeftResizing = false;
            document.body.style.cursor = '';
            document.body.classList.remove('no-select');
            try {
                localStorage.setItem('leftPaneWidth', leftPane.style.width);
            } catch (e) {
                // Ignore
            }
        }
    });

    // Restore widths
    try {
        const savedWidth = localStorage.getItem('tocWidth');
        if (savedWidth) {
            tocPane.style.width = savedWidth;
        }
    } catch (e) {
        // Ignore
    }
    try {
        const savedLeftPaneWidth = localStorage.getItem('leftPaneWidth');
        if (savedLeftPaneWidth && leftPane) {
            leftPane.style.width = savedLeftPaneWidth;
        }
    } catch (e) {
        // Ignore
    }
});
