importScripts('/static/js/highlight.min.js');

onmessage = function (event) {
  try {
    const result = hljs.highlightAuto(event.data);
    postMessage(result.value);
  } catch (error) {
    console.error('Highlighting error:', error);
    // Fallback: return original data if highlighting fails
    postMessage(event.data);
  }
};