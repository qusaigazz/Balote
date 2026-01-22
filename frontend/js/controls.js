export function setupControls(maxStep, onStepChange) {
  let step = 0;
  let playing = false;
  let timer = null;
  let speed = 1;

  const slider = document.getElementById("slider");
  slider.max = maxStep;

  function setStep(s) {
    step = Math.max(0, Math.min(maxStep, s));
    slider.value = step;
    document.getElementById("step-label").textContent = step;
    onStepChange(step);
  }

  const prevBtn = document.getElementById("prev");
  const nextBtn = document.getElementById("next");
  const playBtn = document.getElementById("play");

  prevBtn.onclick = () => setStep(step - 1);
  nextBtn.onclick = () => setStep(step + 1);

  function setPlayIcon() {
    playBtn.textContent = playing ? "⏸" : "▶";
  }

  function startTimer() {
    clearInterval(timer);
    timer = setInterval(() => {
      if (step >= maxStep) {
        clearInterval(timer);
        playing = false;
        setPlayIcon();
        return;
      }
      setStep(step + 1);
    }, 500 / speed);
  }

  playBtn.onclick = () => {
    if (playing) {
      clearInterval(timer);
      playing = false;
      setPlayIcon();
    } else {
      playing = true;
      startTimer();
      setPlayIcon();
    }
  };

  slider.oninput = () => setStep(Number(slider.value));

  const speedSelect = document.getElementById("speed-select");
  if (speedSelect) {
    speed = Number(speedSelect.value) || 1;
    speedSelect.onchange = () => {
      speed = Number(speedSelect.value) || 1;
      if (playing) {
        startTimer();
      }
    };
  }

  return setStep;
}
