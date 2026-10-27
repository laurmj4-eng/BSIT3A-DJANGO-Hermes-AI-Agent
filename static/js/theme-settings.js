/*!
 * Theme settings offcanvas: live theme switching + reset.
 * localStorage keys (shared with js/tabler-theme.js — do not rename):
 *   tabler-theme, tabler-theme-base, tabler-theme-font,
 *   tabler-theme-primary, tabler-theme-radius
 */
(function () {
	"use strict";

	var themeConfig = {
		theme: "light",
		"theme-base": "gray",
		"theme-font": "sans-serif",
		"theme-primary": "indigo",
		"theme-radius": "1",
	};

	document.addEventListener("DOMContentLoaded", function () {
		var form = document.getElementById("offcanvasSettings");
		var resetButton = document.getElementById("reset-changes");

		if (!form || !resetButton) {
			return;
		}

		var url = new URL(window.location);

		var checkItems = function () {
			for (var key in themeConfig) {
				var value =
					window.localStorage.getItem("tabler-" + key) || themeConfig[key];
				var radios = form.querySelectorAll('[name="' + key + '"]');

				radios.forEach(function (radio) {
					radio.checked = radio.value === value;
				});
			}
		};

		form.addEventListener("change", function (event) {
			var target = event.target;
			var name = target.name;
			var value = target.value;

			if (Object.prototype.hasOwnProperty.call(themeConfig, name)) {
				document.documentElement.setAttribute("data-bs-" + name, value);
				window.localStorage.setItem("tabler-" + name, value);
				url.searchParams.set(name, value);
				window.history.pushState({}, "", url);
			}
		});

		resetButton.addEventListener("click", function () {
			for (var key in themeConfig) {
				document.documentElement.removeAttribute("data-bs-" + key);
				window.localStorage.removeItem("tabler-" + key);
				url.searchParams.delete(key);
			}

			checkItems();

			window.history.pushState({}, "", url);
		});

		checkItems();
	});
})();
