/**
 * Plugin Template — entry point
 *
 * Exports a singleton plugin instance.
 * PluginManager loads this via: const plugin = require(entryPath).default || require(entryPath)
 */
import { MyPlugin } from './src/my-plugin';

export default new MyPlugin();
