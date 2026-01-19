const express = require('express');
const path = require('path');
const app = express();
const port = 3000;

// Serve static files from the build directory
app.use(express.static(path.join(__dirname, 'build')));

// Handle all other routes by returning index.html (SPA fallback)
// Using regex pattern for Express 5 compatibility
app.get(/.*/, (req, res) => {
    const indexFile = path.join(__dirname, 'build', 'index.html');
    res.sendFile(indexFile, (err) => {
        if (err) {
            console.error("Error sending index.html:", err);
            res.status(500).send("Error loading application.");
        }
    });
});

app.listen(port, () => {
    console.log(`✅ SPA Server running on port ${port}`);
    console.log(`📂 Serving files from ${path.join(__dirname, 'build')}`);
});
