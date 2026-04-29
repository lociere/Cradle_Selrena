/**
 * 插件入口 — index.ts
 *
 * 【必须存在】导出插件定义。
 * PluginManager 同时兼容：
 *   1. 直接导出插件实例
 *   2. 使用 defineExtension() 导出带补充元数据的定义对象
 *
 * 规范：
 *   - 此文件只做一件事：实例化并导出插件类/定义
 *   - 不要在此文件里写任何业务逻辑
 */
import { defineExtension } from '@cradle-selrena/plugin-sdk';
import { MyPlugin } from './src/my-plugin';

export default defineExtension({
	manifest: {
		activationEvents: ['onStartup'],
		contributes: {
			commands: [
				{
					command: 'my-plugin.ping',
					title: 'Ping My Plugin',
					category: 'My Plugin',
				},
			],
		},
	},
	plugin: new MyPlugin(),
});
