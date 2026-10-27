/* Pre-paint theme setup: mirrors the storage keys used by static/js/tabler-theme.js
   so the chosen theme is applied before the stylesheets render. */
(function () {
  'use strict';

  var defaults = {
    theme: 'light',
    'theme-base': 'gray',
    'theme-font': 'sans-serif',
    'theme-primary': 'indigo',
    'theme-radius': '1'
  };

  Object.keys(defaults).forEach(function (key) {
    var stored = null;
    try {
      stored = window.localStorage.getItem('tabler-' + key);
    } catch (error) {
      stored = null;
    }
    var value = stored || defaults[key];
    var attribute = 'data-bs-' + key;
    if (value !== defaults[key]) {
      document.documentElement.setAttribute(attribute, value);
    } else {
      document.documentElement.removeAttribute(attribute);
    }
  });
})();
