/**
 * exercises.js
 * Renders stretching routines for posture correction
 */

const EXERCISES = [
  {
    title: "Chin Tucks",
    target: "Neck & Upper Spine",
    desc: "Sit straight, look forward. Retract your chin backwards like you're making a double chin. Hold for 5 seconds.",
    reps: "10 reps",
    icon: "👤"
  },
  {
    title: "Chest Opener Stretch",
    target: "Shoulders & Chest",
    desc: "Clasp your hands behind your back, squeeze your shoulder blades together, and gently lift your arms. Hold for 15-30s.",
    reps: "3 sets",
    icon: "🫁"
  },
  {
    title: "Thoracic Extension",
    target: "Mid Back",
    desc: "Sit in a chair with a short back. Interlace hands behind your head and gently lean back over the chair.",
    reps: "5 reps",
    icon: "🪑"
  },
  {
    title: "Wall Angels",
    target: "Upper Back & Shoulders",
    desc: "Stand with back flat against a wall. Raise arms to shoulder height, bend elbows 90°. Slide arms up and down the wall.",
    reps: "10-15 reps",
    icon: "👼"
  }
];

function renderExercises() {
  const container = document.getElementById('exercisesList');
  if (!container) return;

  container.innerHTML = EXERCISES.map(ex => `
    <div class="exe-card glass-panel">
      <div class="exe-img">${ex.icon}</div>
      <div class="exe-body">
        <h3>${ex.title}</h3>
        <p>${ex.desc}</p>
        <div class="exe-meta">
          <span>🎯 ${ex.target}</span>
          <span>⏱️ ${ex.reps}</span>
        </div>
      </div>
    </div>
  `).join('');
}

document.addEventListener('DOMContentLoaded', renderExercises);
