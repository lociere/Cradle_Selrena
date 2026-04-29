const fs = require('fs');
const path = require('path');

const srcDir = path.join(__dirname, 'src');

// Define exactly what gets moved where (relative to src/)
const moves = {
    // core
    'core/event-bus': 'core/infrastructure/event-bus',
    'core/observability': 'core/infrastructure/logger',
    'core/config': 'core/infrastructure/config',
    'core/utils': 'core/infrastructure/utils',
    // infrastructure
    'infrastructure/ipc': 'core/infrastructure/ipc-broker',
    'infrastructure/persistence': 'core/infrastructure/storage',
    // host
    'modules/plugin/plugin-manager.ts': 'core/host/plugin-manager.ts',
    'modules/plugin/kernel-proxy-impl.ts': 'core/host/bridge-impl/kernel-proxy-impl.ts',
    'modules/plugin/plugin-scene-transcript-service.ts': 'core/application/capabilities/scene/plugin-scene-transcript-service.ts',
    // app capabilities
    'modules/action-stream': 'core/application/capabilities/action-stream',
    'modules/ai': 'core/application/capabilities/inference',
    'modules/audio': 'core/application/capabilities/audio',
    'modules/memory': 'core/application/capabilities/memory',
    'modules/scene': 'core/application/capabilities/scene',
    // domain
    'modules/attention': 'core/domain/attention',
    'modules/life-clock': 'core/domain/organism/life-clock',
};

// Also account for missing stuff since we will create sdk later.
const fileMap = {}; // old absolute path -> new absolute path

function addFileMap(oldPath, newPath) {
    if (fs.statSync(oldPath).isDirectory()) {
        const files = fs.readdirSync(oldPath);
        for (const f of files) {
            addFileMap(path.join(oldPath, f), path.join(newPath, f));
        }
    } else {
        fileMap[oldPath] = newPath;
    }
}

// Build file map map before moving
for (const [oldRel, newRel] of Object.entries(moves)) {
    const oldAbs = path.join(srcDir, oldRel);
    const newAbs = path.join(srcDir, newRel);
    if (fs.existsSync(oldAbs)) {
        addFileMap(oldAbs, newAbs);
    }
}

// Any file not in fileMap stays where it is
function walkAndMap(dir) {
    if (!fs.existsSync(dir)) return;
    const files = fs.readdirSync(dir);
    for (const f of files) {
        const p = path.join(dir, f);
        if (!fileMap[p] && !Object.keys(moves).some(m => p.startsWith(path.join(srcDir, m)))) {
            if (fs.statSync(p).isDirectory()) {
                walkAndMap(p);
            } else {
                fileMap[p] = p; // Stays unchanged
            }
        }
    }
}
walkAndMap(srcDir);

// Now read all contents and update imports in memory
const fileContents = {};
for (const [oldPath, newPath] of Object.entries(fileMap)) {
    if (oldPath.endsWith('.ts')) {
        let content = fs.readFileSync(oldPath, 'utf8');
        
        // Find import/export paths
        const re = /(import\s+.*?from\s+['"])(.*?)(['"].*?)/g;
        // Also match `import { X } from "..."` and `export * from "..."` properly
        const re2 = /((?:import|export)\s+.*?from\s+['"])(.*?)(['"].*?)/g;
        const re3 = /(import\s+['"])(.*?)(['"].*?)/g; // e.g. import "reflect-metadata"

        const replacer = (match, p1, oldImportStr, p3) => {
            if (!oldImportStr.startsWith('.')) return match; // Not a relative import
            
            // resolve old relative import based on old directory
            const oldDir = path.dirname(oldPath);
            let importedTarget = path.resolve(oldDir, oldImportStr);
            
            // check if importedTarget maps to something new.
            // But importedTarget might not have .ts extension.
            let matchedOldTarget = undefined;
            if (fileMap[importedTarget + '.ts']) matchedOldTarget = importedTarget + '.ts';
            else if (fileMap[importedTarget + '.tsx']) matchedOldTarget = importedTarget + '.tsx';
            else if (fileMap[path.join(importedTarget, 'index.ts')]) matchedOldTarget = path.join(importedTarget, 'index.ts');
            else if (fileMap[importedTarget]) matchedOldTarget = importedTarget;

            if (matchedOldTarget) {
                const mappedNewTarget = fileMap[matchedOldTarget];
                // Strip extension for TS
                const cleanMapped = mappedNewTarget.replace(/\.tsx?$/, '').replace(/\\index$/, '');
                
                let newRel = path.relative(path.dirname(newPath), cleanMapped).replace(/\\/g, '/');
                if (!newRel.startsWith('.')) newRel = './' + newRel;
                return p1 + newRel + p3;
            }
            return match; // unable to resolve
        };

        content = content.replace(re2, replacer);
        content = content.replace(re3, replacer);
        
        // Also fix up `@cradle-selrena/protocol` imports. No relative changes needed, but interfaces -> ports
        content = content.replace(/interfaces\/plugin-interface/g, 'ports/bridge');
        content = content.replace(/\/interfaces/g, '/ports');
        content = content.replace(/\/types/g, '/models');

        fileContents[newPath] = content;
    }
}

// Execute moves
function mkdir(dir) {
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, {recursive: true});
}

for (const [oldPath, newPath] of Object.entries(fileMap)) {
    if (oldPath !== newPath) {
        mkdir(path.dirname(newPath));
        if (!oldPath.endsWith('.ts')) {
            // It's a non-ts file, just copy it since we move dirs manually below.
            // Actually we are writing EVERYTHING directly.
            fs.copyFileSync(oldPath, newPath);
        }
    }
}

// Write the transformed .ts files
for (const [newPath, content] of Object.entries(fileContents)) {
    mkdir(path.dirname(newPath));
    fs.writeFileSync(newPath, content, 'utf8');
}

// Delete old empty directories / old files
for (const [oldRel, newRel] of Object.entries(moves)) {
    const oldAbs = path.join(srcDir, oldRel);
    if (fs.existsSync(oldAbs)) {
        fs.rmSync(oldAbs, {recursive: true, force: true});
    }
}

console.log("Migration complete.");
