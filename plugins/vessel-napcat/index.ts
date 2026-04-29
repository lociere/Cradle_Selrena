/**
 * Napcat Vessel Plugin — entry point
 *
 * Exports a singleton plugin instance.
 * PluginManager loads this via: const plugin = require(entryPath).default || require(entryPath)
 */
import { NapcatVesselPlugin } from './src/napcat-vessel-plugin';

export default new NapcatVesselPlugin();
