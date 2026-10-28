# Delivery checklist

- [x] “Build the Frontend Separately — Do Not Modify the Main Repository.”
- [x] “The primary application interface must remain vanilla HTML/CSS/JS. Keep React isolated to chart components.”
- [x] “Use Bklit UI components where technically compatible”; install official registry source and use interactive Bklit bar and line charts with real chart data.
- [x] “Use a minimal, professional, editorial design” with responsive layouts, restrained colors, readable tables, subtle borders, and reduced-motion handling.
- [x] “Make dark mode the default theme on every page. Define reusable CSS design tokens for backgrounds, surfaces, typography, borders, accents, and chart colors. Ensure all components and actual Bklit charts use those tokens consistently.”
- [x] “Apply the dark theme consistently to every Bklit chart: transparent or theme-matched backgrounds; readable axis labels, ticks, legends, and tooltips; subtle gridlines; distinct but restrained series colors; clear contrast for selected points and hover states; consistent typography and spacing across all chart types. Do not leave white chart backgrounds inside dark pages or use default chart colors without checking their contrast and visual consistency.”
- [x] “Check text contrast and keyboard focus visibility. Use smooth, understated transitions for navigation, chart updates, hover states, and expanding panels; keep motion purposeful and support prefers-reduced-motion. Verify the actual rendered application, not just the CSS, to ensure there are no mismatched light components or unreadable charts.”
- [x] “The frontend must be designed to work with the existing Auto-Insight Report Generator features.”
- [x] “Create a clearly documented API contract” for endpoints, payloads, chart data, reports, saved datasets, errors, and progress.
- [x] “Use mock data only to demonstrate the frontend when the backend is unavailable. Keep mock data isolated and make it obvious.”
- [x] “Do not claim that backend functionality works until it has been integrated and tested.”
- [x] Deliver standalone source, Vite config, dependency lock, `.env.example`, `README.md`, `API_CONTRACT.md`, and `INTEGRATION_GUIDE.md`.
- [x] Build the Vite app and verify the demo navigation, data tables, real Bklit chart mounts, Plotly rendering, and browser console.
- [ ] Backend contract routes, Python integration, report persistence/export, and database workflows remain for the user to integrate and test in Antigravity.
