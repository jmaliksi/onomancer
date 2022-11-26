async function vocalize(words) {
    if (!('speechSynthesis' in window)) {
        return;
    }
    let synth = window.speechSynthesis;
    if (synth.speaking) {
        synth.cancel();
    }
    let voice = synth.getVoices().filter((v) => v.default)[0];
    if (!voice) {
        await getPromiseFromEvent(synth, "voiceschanged")
        voice = synth.getVoices().filter((v) => v.default)[0];
    }
    let utterance = new SpeechSynthesisUtterance(words)
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
