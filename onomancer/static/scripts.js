async function vocalize(words) {
    if (!('speechSynthesis' in window)) {
        return;
    }
    let synth = window.speechSynthesis;
    if (synth.speaking) {
        synth.cancel();
    }
    let voice = getVoice();
    if (!voice) {
        const voiceChanged = getPromiseFromEvent(synth, "voiceschanged")
        const timeout = timerPromise(100)
        await Promise.any([voiceChanged, timeout])
        voice = getVoice();
    }
    let textarea = document.createElement("textarea");
    textarea.innerHTML = words;
    let utterance = new SpeechSynthesisUtterance(textarea.value)
    utterance.voice = voice;
    synth.speak(utterance);
}

function getPromiseFromEvent(item, event) {
    return new Promise((resolve) => {
        const listener = () => {
            item.removeEventListener(event, listener);
            resolve();
        }
        item.addEventListener(event, listener);
    });
}

function getVoice() {
    return window.speechSynthesis.getVoices().filter((v) => v.default && v.lang.startsWith("en-"))[0];
}

function timerPromise(timeout) {
    return new Promise((resolve) => setTimeout(resolve, timeout));
}
