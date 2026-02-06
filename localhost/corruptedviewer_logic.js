// San Francisco SmartTranscripts - Viewer Logic (Final Architecture)
// This script "hydrates" a static HTML page to make it interactive.

let selectionStartTime = 0;
let selectionEndTime = 0;
// Global pointer to the active player (HTML5 video or YouTube)
window.activeVideoPlayer = null;


function formatTime(seconds) {
    const h = Math.floor(seconds / 3600).toString().padStart(2, '0');
    const m = Math.floor((seconds % 3600) / 60).toString().padStart(2, '0');
    const s = Math.floor(seconds % 60).toString().padStart(2, '0');
    return `${h}:${m}:${s}`;
}

// --- Click-based Dropdown Logic ---
function setupDropdownMenus() {
    const menuItems = document.querySelectorAll('.menu-item');

    menuItems.forEach(menuItem => {
        const button = menuItem.querySelector('button');
        if (button && !button.dataset.listenerAttached) {
            button.dataset.listenerAttached = 'true'; // mark as done

            button.addEventListener('click', event => {
                event.stopPropagation();
                const isAlreadyOpen = menuItem.classList.contains('menu-open');

                document.querySelectorAll('.menu-item').forEach(item => {
                    item.classList.remove('menu-open');
                });

                if (!isAlreadyOpen) {
                    menuItem.classList.add('menu-open');
                }
            });
        }
    });

    // Attach window listener once
    if (!window.dropdownCloseListenerAttached) {
        window.addEventListener('click', () => {
            document.querySelectorAll('.menu-item').forEach(item => {
                item.classList.remove('menu-open');
            });
        });
        window.dropdownCloseListenerAttached = true;
    }
}

function updatePlayerForTime(startTimeParam, endTimeParam) {
    setTimeout(() => {
        const video = window.activeVideoPlayer || document.getElementById('videoElement');
        if (!video) return;

        const allUtterances = Array.from(document.querySelectorAll('.utterance'));
        if (allUtterances.length === 0) return;

        const targetStartTime = parseFloat(startTimeParam);
        const targetEndTime = parseFloat(endTimeParam);

        const startSpan = allUtterances.slice().reverse().find(s => parseFloat(s.dataset.startTime) <= targetStartTime);

        if (startSpan) {
            const startSpanIndex = allUtterances.findIndex(s => s === startSpan);
            let endSpan;

            const nextSpanIndex = allUtterances.findIndex((s, index) => index >= startSpanIndex && parseFloat(s.dataset.startTime) > targetEndTime);

            if (nextSpanIndex !== -1) {
                endSpan = allUtterances[nextSpanIndex - 1];
                selectionEndTime = parseFloat(allUtterances[nextSpanIndex].dataset.startTime);
            } else {
                endSpan = allUtterances[allUtterances.length - 1];
                selectionEndTime = video.duration;
            }

            if (endSpan) {
                selectionStartTime = parseFloat(startSpan.dataset.startTime);
                const nextSpanAfterEnd = allUtterances[allUtterances.findIndex(s => s === endSpan) + 1];
                if (nextSpanAfterEnd) {
                    selectionEndTime = parseFloat(nextSpanAfterEnd.dataset.startTime);
                } else {
                    selectionEndTime = video.duration;
                }
                const timeRangeDisplay = document.getElementById('time-range');
                const playClipButton = document.getElementById('play-clip-button');
                timeRangeDisplay.textContent = `Clip: ${formatTime(selectionStartTime)} - ${formatTime(selectionEndTime)}`;
                playClipButton.disabled = false;
                video.currentTime = selectionStartTime;
                const newRange = document.createRange();
                newRange.setStart(startSpan.firstChild, 0);
                newRange.setEnd(endSpan.lastChild, endSpan.lastChild.length);
                window.getSelection().removeAllRanges();
                window.getSelection().addRange(newRange);
                startSpan.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }
    }, 500);
}
function updatePlayerForRange(range) {
    //const video = document.getElementById('videoElement');
    const video = window.activeVideoPlayer;

    const timeRangeDisplay = document.getElementById('time-range');
    const playClipButton = document.getElementById('play-clip-button');

    let startSpan = range.startContainer.parentElement.closest('.utterance');
    let endSpan = range.endContainer.parentElement.closest('.utterance');

    // --- Find the TRUE start of the selection ---
    if (!startSpan) {
        const startElement = range.startContainer.parentElement;
        const parentP = startElement.closest('p');
        if (parentP) {
            // The selection started on a speaker name. The intended start is the
            // first utterance that follows the speaker name within the same <p>.
            startSpan = parentP.querySelector('.utterance');
        }
    }

    // --- Find the TRUE end of the selection ---
    if (!endSpan) {
        const endElement = range.endContainer.parentElement;
        const parentP = endElement.closest('p');
        if (parentP) {
            // The selection ended on a speaker name. The intended end is the
            // LAST utterance within that same speaker's block.
            const utterancesInBlock = parentP.querySelectorAll('.utterance');
            if (utterancesInBlock.length > 0) {
                endSpan = utterancesInBlock[utterancesInBlock.length - 1];
            }
        }
    }

    // If the selection ends at the very beginning of the next span,
    // the user almost certainly meant to select up to the end of the previous one.
    if (range.endOffset === 0 && endSpan && endSpan.previousElementSibling) {
        const prevSibling = endSpan.previousElementSibling;
        if (prevSibling && prevSibling.matches('.utterance')) {
            endSpan = prevSibling;
        }
    }

    if (startSpan && endSpan) {
        selectionStartTime = parseFloat(startSpan.dataset.startTime);

        const allUtterances = Array.from(document.querySelectorAll('.utterance'));
        const endSpanIndex = allUtterances.findIndex(span => span === endSpan);

        if (endSpanIndex !== -1 && endSpanIndex + 1 < allUtterances.length) {
            const nextSpan = allUtterances[endSpanIndex + 1];
            selectionEndTime = parseFloat(nextSpan.dataset.startTime);
        } else {
            selectionEndTime = parseFloat(endSpan.dataset.endTime) || video.duration;
        }

        video.currentTime = selectionStartTime;
        timeRangeDisplay.textContent = `Clip: ${formatTime(selectionStartTime)} - ${formatTime(selectionEndTime)}`;
        playClipButton.disabled = false;

        const newRange = document.createRange();
        newRange.setStart(startSpan.firstChild, 0);
        newRange.setEnd(endSpan.lastChild, endSpan.lastChild.length);
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(newRange);
    }
}


document.addEventListener('DOMContentLoaded', () => {
    const urlParams = new URLSearchParams(window.location.search);
    // Removed printable param check


    console.log("Viewer logic initialized.");



    // --- App State ---
    const dataIsland = document.getElementById('meeting-data');
    if (!dataIsland) {
        console.error("Meeting data island not found.");
        return;
    }
    window.meetingData = JSON.parse(dataIsland.textContent);
    const textContainer = document.getElementById('text-container');


    const shareTargets = {
        email: {
            label: "Email",
            svg: `<svg viewBox="0 0 24 24"><path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/></svg>`,
            action: (url, subject) => `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent("View the transcript: " + url)}`
        },
        copy: {
            label: "Copy Link",
            svg: `<svg viewBox="0 0 24 24"><path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg>`,
            action: (url, subject, button) => {
                navigator.clipboard.writeText(url).then(() => {
                    const originalText = button.innerHTML;
                    button.innerHTML = `<span>Copied!</span>`;
                    button.disabled = true;
                    setTimeout(() => {
                        button.innerHTML = originalText;
                        button.disabled = false;
                    }, 2000);
                });
                return null; // No new window
            }
        },
        facebook: {
            label: "Facebook",
            svg: `<svg viewBox="0 0 24 24"><path d="M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2-2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2m13 2h-2.5a3.5 3.5 0 0 0-3.5 3.5V11h-2v3h2v7h3v-7h3v-3h-3V8.5A1.5 1.5 0 0 1 15 7h3V5z"/></svg>`,
            action: (url, subject) => `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}&quote=${encodeURIComponent(subject)}`
        },
        x: {
            label: "X",
            svg: `<svg viewBox="0 0 24 24"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>`,
            action: (url, subject) => `https://twitter.com/intent/tweet?url=${encodeURIComponent(url)}&text=${encodeURIComponent(subject)}`
        },
        linkedin: {
            label: "LinkedIn",
            svg: `<svg viewBox="0 0 24 24"><path d="M19 3a2 2 0 0 1 2 2v14a2 2 0 0 1-2-2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h14m-11 4H5v11h3V7m-1.5-2a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3m11 2h-2.5c-2 0-2.5 1-2.5 2.5V11h3v3h-3v5h-3v-5H9v-3h2.5V9.5C11.5 7 13 6 15 6h2.5v3z"/></svg>`,
            action: (url, subject) => `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}`
        },
        whatsapp: {
            label: "WhatsApp",
            svg: `<svg viewBox="0 0 24 24"><path d="M12.04 2c-5.46 0-9.91 4.45-9.91 9.91 0 1.75.46 3.45 1.32 4.95L2 22l5.25-1.38c1.45.79 3.08 1.21 4.79 1.21 5.46 0 9.91-4.45 9.91-9.91S17.5 2 12.04 2zM12.04 20.15c-1.48 0-2.93-.4-4.2-1.15l-.3-.18-3.12.82.83-3.04-.2-.31c-.82-1.31-1.26-2.83-1.26-4.38 0-4.54 3.7-8.24 8.24-8.24 4.54 0 8.24 3.7 8.24 8.24s-3.7 8.24-8.24 8.24zm4.52-6.13c-.25-.12-1.47-.72-1.7-.81-.23-.09-.39-.12-.56.12-.17.25-.64.81-.78.97-.14.17-.29.19-.54.06-.25-.12-1.06-.39-2.02-1.25-.75-.67-1.25-1.5-1.4-1.75-.14-.25-.02-.38.11-.51.11-.11.25-.29.37-.43.13-.14.17-.25.25-.41.09-.17.04-.31-.02-.43s-.56-1.34-.76-1.84c-.2-.48-.41-.42-.56-.42h-.48c-.17 0-.43.06-.66.31-.22.25-.86.85-.86 2.07 0 1.22.88 2.4 1 2.56.12.17 1.76 2.67 4.25 3.73.59.25 1.05.41 1.41.52.6.19 1.14.16 1.56.1.48-.07 1.47-.6 1.67-1.18.21-.58.21-1.07.14-1.18-.05-.12-.2-.19-.44-.31z"/></svg>`,
            action: (url, subject) => `https://api.whatsapp.com/send?text=${encodeURIComponent(subject + ": " + url)}`
        }
    };

    // --- Search Functionality ---
    let searchableTextMap = null;
    let lastSearch = {
        query: "",
        startIndex: 0
    };

    function getSearchableTextMap() {
        if (searchableTextMap) return searchableTextMap;

        let fullText = "";
        const map = []; // Maps character index to its corresponding text node
        const walker = document.createTreeWalker(textContainer, NodeFilter.SHOW_TEXT);
        let node;
        while (node = walker.nextNode()) {
            const start = fullText.length;
            fullText += node.textContent;
            for (let i = start; i < fullText.length; i++) {
                map[i] = { node: node, offset: i - start };
            }
        }
        searchableTextMap = { fullText: fullText.toLowerCase(), map };
        return searchableTextMap;
    }



    // --- Initialization ---
    window.scrollTo(0, 0);
    buildMenusAndPlayer();
    loadNavigationModule();

    const videoUrl = meetingData.video_url;
    const isYouTube = videoUrl.includes('youtube.com') || videoUrl.includes('youtu.be');

    // Utility to extract the YouTube video ID
    function extractYouTubeId(url) {
        const match = url.match(/[?&]v=([^&]+)|youtu\.be\/([^?&]+)/);
        return match ? (match[1] || match[2]) : null;
    }

    if (isYouTube) {
        // --- YOUTUBE MODE (adds player dynamically) ---
        const videoId = extractYouTubeId(videoUrl);
        const videoContainer = document.getElementById('video-player-container');
        document.body.classList.add('youtube-player-active');

        const wrapper = document.getElementById('player-wrapper');
        if (wrapper) {
            wrapper.innerHTML = '<div id="playerContainer"></div>';
        } else {
            videoContainer.innerHTML = '<div id="playerContainer"></div>'; // fallback if wrapper missing
        }

        const initYouTubePlayer = () => {
            const ytPlayer = new VideoPlay(videoId, 'playerContainer');

            // Wait until the player is fully ready
            ytPlayer.addEventListener('ready', () => {
                window.activeVideoPlayer = ytPlayer;   // ✅ fallback reference
                setupInteractiveTranscript(ytPlayer);
            });
        };


        // Load /youtubePlayer.js if needed
        if (typeof window.VideoPlay === 'undefined') {
            const script = document.createElement('script');
            script.src = '/youtubePlayer.js';
            document.head.appendChild(script);
            script.onload = initYouTubePlayer;
        } else {
            initYouTubePlayer();
        }

    } else {
        // --- NON-YOUTUBE MODE (exactly as before) ---
        // Use the <video id="videoElement"> that already exists in the static HTML
        const videoElement = document.getElementById('videoElement');
        if (videoElement) {
            window.activeVideoPlayer = videoElement;  // ✅ fallback reference
            setupHlsPlayer(videoElement, videoUrl);
            setupInteractiveTranscript(videoElement);
        }
    }



    setupMenuAndModalListeners();
    handleUrlParameters();

    // --- Helper Functions ---


    function setupHlsPlayer(videoElement, videoUrl) {
        if (Hls.isSupported()) {
            const hls = new Hls();
            hls.loadSource(videoUrl);
            hls.attachMedia(videoElement);
        } else if (videoElement.canPlayType('application/vnd.apple.mpegurl')) {
            videoElement.src = videoUrl;
        }
    }

    function generateTranscriptText() {
        let text = `${document.getElementById('meeting-title').textContent}\n\n`;
        const paragraphs = textContainer.querySelectorAll('p');
        paragraphs.forEach(p => {
            const speaker = p.querySelector('strong');
            if (speaker) {
                text += speaker.textContent + ' ';
            }
            const utterances = p.querySelectorAll('.utterance');
            utterances.forEach(u => {
                text += u.textContent;
            });
            text += '\n\n';
        });
        return text.trim();
    }

    // setupPrintableView removed


    // --- UI Building ---
    function buildMenusAndPlayer() {
        const menuContainer = document.getElementById('viewer-menu');
        const videoPlayerContainer = document.getElementById('video-player-container');
        if (!menuContainer || !videoPlayerContainer) return;

        const menuHTML = `
            <div class="menu-item"><button>File</button>
                <ul class="dropdown-menu">
                    <li id="print-button">Print Transcript</li>
                    <li id="save-button">Download Transcript (.txt)</li>
                </ul>
            </div>
            <button id="share-button">Share Transcript</button>

        `;
        menuContainer.innerHTML = menuHTML;

        const playIconSVG = '<svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>';
        const pauseIconSVG = '<svg viewBox="0 0 24 24"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>';
        const restartIconSVG = '<svg viewBox="0 0 24 24"><path d="M12 5V1L7 6l5 5V7c3.31 0 6 2.69 6 6s-2.69 6-6 6-6-2.69-6-6H4c0 4.42 3.58 8 8 8s8-3.58 8-8-3.58-8-8-8z"/></svg>';

        videoPlayerContainer.innerHTML = `
            <div id="time-range">Select text to play a clip.</div>
            <div id="player-controls">
                <button id="play-clip-button" class="icon-button" disabled title="Play Clip">${playIconSVG}</button>
                <button id="play-full-video-button" class="icon-button" title="Play Full Video">${restartIconSVG}</button>
            </div>
            <div id="player-wrapper"><video id="videoElement"></video></div>
        `;
        buildShareButtons();
        setupDropdownMenus(); // Activate the dropdowns
    }

    function loadNavigationModule() {
        // --- 1️⃣ Load tour assets first (unconditionally) ---
        const css = document.createElement('link');
        css.rel = 'stylesheet';
        css.href = '/tour.css';
        document.head.appendChild(css);

        const tourScript = document.createElement('script');
        tourScript.src = '/tour.js';
        tourScript.defer = true;

        tourScript.onload = () => {
            console.log('Tour module ready.');

            // --- 2️⃣ Then load navigation.js ---
            const navScript = document.createElement('script');
            navScript.src = '/navigation.js';
            navScript.defer = true;
            navScript.onload = () => {
                if (typeof initializeNavigationPane === 'function') {
                    initializeNavigationPane();
                } else {
                    console.error('Navigation module failed to define initializeNavigationPane function.');
                }
            };
            document.body.appendChild(navScript);
        };

        tourScript.onerror = () => console.error('Failed to load /tour.js');
        document.body.appendChild(tourScript);
    }


    function buildShareButtons() {

        const shareButtonsContainer = document.getElementById('share-buttons');
        if (!shareButtonsContainer) return;

        shareButtonsContainer.innerHTML = ''; // Clear any existing buttons
        for (const [site, config] of Object.entries(shareTargets)) {
            const button = document.createElement('button');
            button.dataset.site = site;
            button.innerHTML = `${config.svg}<span>${config.label}</span>`;
            shareButtonsContainer.appendChild(button);
        }
    }


    // --- Event Listeners & Actions ---
    function setupMenuAndModalListeners() {
        const agendaNav = document.getElementById('agenda');
        const shareModal = document.getElementById('share-modal');
        const closeModalButtons = document.querySelectorAll('.close-button');
        const shareButtons = document.getElementById('share-buttons');
        //const findTextButton = document.getElementById('find-text-button');
        const findNextButton = document.getElementById('find-next-button');
        //const speakerSubmenu = document.getElementById('speaker-submenu');
        const printButton = document.getElementById('print-button');
        const saveButton = document.getElementById('save-button');
        const shareButton = document.getElementById('share-button');
        //const aboutButton = document.getElementById('about-button');


        closeModalButtons.forEach(btn => btn.addEventListener('click', () => {
            shareModal.style.display = 'none';
            const aboutModal = document.getElementById('about-modal');
            if (aboutModal) aboutModal.style.display = 'none';
        }));

        if (shareButtons) {
            shareButtons.addEventListener('click', handleShare);
        }



        printButton.addEventListener('click', () => {
            window.print();
        });

        saveButton.addEventListener('click', () => {
            const text = generateTranscriptText();
            const blob = new Blob([text], { type: 'text/plain' });
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = `${document.title}.txt`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        });

        shareButton.addEventListener('click', () => {
            const isClip = !window.getSelection().isCollapsed;
            showShareModal(isClip);
        });

        agendaNav.addEventListener('click', (e) => {
            if (e.target.tagName === 'A') {
                e.preventDefault();
                //const video = document.getElementById('videoElement');
                const video = window.activeVideoPlayer;
                const allUtterances = Array.from(document.querySelectorAll('.utterance'));
                if (allUtterances.length === 0) return;

                const timeStringToSeconds = (timeStr) => {
                    const parts = timeStr.split(':').map(Number);
                    return parts.length === 3 ? parts[0] * 3600 + parts[1] * 60 + parts[2] : 0;
                };

                const clickedLi = e.target.closest('li');
                if (!clickedLi) return;

                let startTime;
                const href = e.target.getAttribute('href');
                const startTimeMatch = e.target.textContent.match(/\((\d{2}:\d{2}:\d{2})\)/);

                if (!startTimeMatch) {
                    if (href === '#item-0') {
                        startTime = 0;
                    } else {
                        return;
                    }
                } else {
                    startTime = timeStringToSeconds(startTimeMatch[1]);
                }

                let endTime;
                const nextLi = clickedLi.nextElementSibling;
                if (nextLi) {
                    const nextLink = nextLi.querySelector('a');
                    const endTimeMatch = nextLink ? nextLink.textContent.match(/\((\d{2}:\d{2}:\d{2})\)/) : null;
                    endTime = endTimeMatch ? timeStringToSeconds(endTimeMatch[1]) : (video ? video.duration : 0);
                } else {
                    endTime = video ? video.duration : 0;
                }

                let startSpan = allUtterances.slice().reverse().find(s => parseFloat(s.dataset.startTime) <= startTime);

                if (!startSpan && allUtterances.length > 0) {
                    startSpan = allUtterances[0];
                }

                if (startSpan) {
                    const startSpanIndex = allUtterances.findIndex(s => s === startSpan);
                    let endSpan;
                    const nextSpanIndex = allUtterances.findIndex((s, index) => index >= startSpanIndex && parseFloat(s.dataset.startTime) > endTime);

                    if (nextSpanIndex !== -1) {
                        endSpan = allUtterances[nextSpanIndex - 1];
                    } else {
                        endSpan = allUtterances[allUtterances.length - 1];
                    }

                    if (endSpan) {
                        const newRange = document.createRange();
                        newRange.setStart(startSpan.firstChild, 0);
                        newRange.setEnd(endSpan.lastChild, endSpan.lastChild.length);
                        window.getSelection().removeAllRanges();
                        window.getSelection().addRange(newRange);
                        updatePlayerForRange(newRange);
                        startSpan.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }
                }
            }
        });
    }

    function showShareModal(isClip) {
        const shareModal = document.getElementById('share-modal');
        const shareClipOptions = document.getElementById('share-clip-options');
        const shareClipCheckbox = document.getElementById('share-clip-checkbox');
        const shareTimeRange = document.getElementById('share-time-range');

        if (isClip) {
            shareClipOptions.style.display = 'block';
            shareClipCheckbox.checked = true;
            shareTimeRange.textContent = `(${formatTime(selectionStartTime)} - ${formatTime(selectionEndTime)})`;
        } else {
            shareClipOptions.style.display = 'none';
            shareClipCheckbox.checked = false;
        }
        shareModal.style.display = 'flex';
    }



    function handleShare(e) {
        const button = e.target.closest('button');
        if (!button) return;

        const site = button.dataset.site;
        if (!site || !shareTargets[site]) return;

        let url = window.location.href.split('?')[0];
        const subject = document.title;

        if (document.getElementById('share-clip-checkbox').checked) {
            url += `?startTime=${selectionStartTime}&endTime=${selectionEndTime}`;
        }

        const targetUrl = shareTargets[site].action(url, subject, button);

        if (targetUrl) {
            window.open(targetUrl, '_blank');
        }

        // Don't close the modal immediately for the copy action
        if (site !== 'copy') {
            document.getElementById('share-modal').style.display = 'none';
        }
    }

    function handleUrlParameters() {
        const startTimeParam = urlParams.get('startTime');
        const endTimeParam = urlParams.get('endTime');
        const q = urlParams.get('q');
        const agendaItem = urlParams.get('agenda');

        if (agendaItem) {
            // Use a short timeout to ensure the rest of the page has loaded
            setTimeout(() => {
                const agendaLink = document.querySelector(`#agenda a[href="#${agendaItem}"]`);
                if (agendaLink) {
                    agendaLink.click();
                }
            }, 100);
        } else if (startTimeParam && endTimeParam) {
            updatePlayerForTime(startTimeParam, endTimeParam);
        }
    }

    function setupInteractiveTranscript(video) {
        const timeRangeDisplay = document.getElementById('time-range');
        const playClipButton = document.getElementById('play-clip-button');
        const playFullVideoButton = document.getElementById('play-full-video-button');
        let clipPlaying = false;

        const playIconSVG = '<svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>';
        const pauseIconSVG = '<svg viewBox="0 0 24 24"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>';

        textContainer.addEventListener('mouseup', () => {
            const selection = window.getSelection();
            if (selection.rangeCount > 0 && !selection.isCollapsed) {
                const range = selection.getRangeAt(0);
                updatePlayerForRange(range);
            }
        });

        document.addEventListener('selectionchange', () => {
            const selection = window.getSelection();
            const shareButton = document.getElementById('share-button');
            if (selection.isCollapsed) {
                shareButton.textContent = 'Share Transcript';
            } else {
                shareButton.textContent = 'Share Clip';
            }
        });

        playClipButton.addEventListener('click', () => {
            if video.paused) {
                video.currentTime = selectionStartTime;
                video.play();
            } else {
                video.pause();
            }
        });

        playFullVideoButton.addEventListener('click', () => {
            const allUtterances = document.querySelectorAll('.utterance');
            if (allUtterances.length > 0) {
                const firstUtterance = allUtterances[0];
                const lastUtterance = allUtterances[allUtterances.length - 1];

                const newRange = document.createRange();
                newRange.setStart(firstUtterance.firstChild, 0);
                newRange.setEnd(lastUtterance.lastChild, lastUtterance.lastChild.length);

                const selection = window.getSelection();
                selection.removeAllRanges();
                selection.addRange(newRange);
                updatePlayerForRange(newRange);

                playClipButton.click();
            }
        });
        const END_TOLERANCE = 1.00; // seconds - kluge for drift
        video.addEventListener('timeupdate', () => {
            if (clipPlaying && video.currentTime >= (selectionEndTime + END_TOLERANCE)) {
                video.pause();
            }
        });

        video.addEventListener('play', () => {
            textContainer.classList.add('no-select');
            clipPlaying = true; // Assume any play could be a clip
            playClipButton.innerHTML = pauseIconSVG;
        }
        );

        video.addEventListener('pause', () => {
            clipPlaying = false;
            textContainer.classList.remove('no-select');
            playClipButton.innerHTML = playIconSVG;
        });
    }


});
