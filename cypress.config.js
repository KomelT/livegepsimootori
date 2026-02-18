const { defineConfig } = require("cypress");

module.exports = defineConfig({
	chromeWebSecurity: true,
	e2e: {
		// We've imported your old cypress plugins here.
		// You may want to clean this up later by importing these.
		setupNodeEvents(on, config) {
			return require("./cypress/plugins/index.js")(on, config);
		},
		baseUrl: "https://dashboard.test.meshtrail.si",
	},
	component: {
		devServer: {
			framework: "create-react-app",
			bundler: "webpack",
		},
	},
	pageLoadTimeout: 10000,
	video: true,
});
