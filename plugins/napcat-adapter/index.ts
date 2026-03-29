/**
 * Napcat Adapter Plugin — entry point
 *
 * Exports a singleton plugin instance.
 * PluginManager loads this via: const plugin = require(entryPath).default || require(entryPath)
 */
import { NapcatAdapterPlugin } from './src/napcat-adapter-plugin';

export default new NapcatAdapterPlugin();
