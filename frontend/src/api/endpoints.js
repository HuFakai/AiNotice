/**
 * 平台 API 端点清单（接口文档页与接口测试页共用，单一数据源）
 *
 * - path 中 `{xxx}` 为路径参数；`?a=` 前缀形式为查询参数
 * - body 为该端点的请求体示例（JSON 字符串），测试页据此预填
 */

export const API_ENDPOINTS = [
  {
    method: 'POST',
    path: '/speak',
    desc: '播放文字（支持单设备与多设备数组）',
    perm: 'speak',
    body: {
      text: '你好，这是一条测试播报',
      device_id: '',
      volume: 80,
    },
  },
  { method: 'GET', path: '/speak/devices', desc: '获取当前账号下的设备列表', perm: 'get_devices' },
  { method: 'GET', path: '/speak/{device_id}', desc: '获取单个设备详情与状态', perm: 'get_status' },
  {
    method: 'POST',
    path: '/speak/{device_id}',
    desc: '向指定设备下发播报',
    perm: 'speak',
    body: { text: '指定设备测试播报' },
  },
  {
    method: 'POST',
    path: '/speak/{device_id}/volume?volume=0-100',
    desc: '设置设备音量（0 是合法值）',
    perm: 'set_volume',
  },
  { method: 'POST', path: '/speak/stop?device_id=', desc: '停止指定设备的播报', perm: 'stop_speak' },
  { method: 'GET', path: '/speak/status/{task_id}', desc: '查询播报任务状态', perm: 'get_status' },
  { method: 'POST', path: '/speak/devices/scan', desc: '强制刷新设备缓存', perm: 'manage_devices', body: {} },
  {
    method: 'POST',
    path: '/notify/send',
    desc: '统一推送：显式指定渠道，或不带渠道参数时发到密钥绑定的全部启用渠道',
    perm: 'send_notify',
    body: {
      title: '接口测试通知',
      content: '通过统一推送发送的测试消息',
      // channel_id: 1,        // 可选：显式指定渠道（覆盖密钥绑定）
      // channel_type: 'webhook',
      // config: { url: 'https://example.com/hook' },
      // recipient: '',        // 可选：覆盖渠道默认目标
      // extra: { volume: 80 },
    },
  },
]

/** 解析 path：返回 { cleanPath, pathParams: [名称], queryKeys: [名称] } */
export function parseEndpointPath(path) {
  let cleanPath = path
  const pathParams = []
  const queryKeys = []

  const qIdx = path.indexOf('?')
  if (qIdx !== -1) {
    const queryPart = path.slice(qIdx + 1)
    cleanPath = path.slice(0, qIdx)
    queryPart.split('&').forEach((pair) => {
      const raw = pair.split('=')[0] || ''
      const key = raw.replace(/=.*$/, '')
      if (key) queryKeys.push(key)
    })
  }

  cleanPath = cleanPath.replace(/\{(\w+)\}/g, (_, name) => {
    pathParams.push(name)
    return `{${name}}`
  })

  return { cleanPath, pathParams, queryKeys }
}
