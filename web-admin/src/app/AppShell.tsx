import { NavLink, Outlet } from 'react-router-dom';

import styles from './AppShell.module.css';
import { useOnline } from './useOnline';
import { useAdminSession } from '../features/auth/adminSessionState';
import type { ProductFeature } from '../api/generated/models/ProductFeature';
import { useReleaseFeatures } from './useReleaseFeatures';

interface NavItem {
  to: string;
  label: string;
  feature?: ProductFeature;
}

const GROUPS: Array<{ label?: string; items: NavItem[] }> = [
  { items: [{ to: '/overview', label: '概览' }] },
  {
    label: '配置',
    items: [
      { to: '/comfy', label: 'ComfyUI 节点', feature: 'comfyui' },
      { to: '/workflows', label: 'Workflows', feature: 'comfyui' },
      { to: '/providers', label: 'LLM Provider' },
      { to: '/default-backend', label: '默认后端' },
    ],
  },
  {
    label: '运行维护',
    items: [
      { to: '/diagnostics', label: '任务诊断' },
      { to: '/storage', label: '存储' },
      { to: '/security', label: 'Token / Security' },
    ],
  },
];

export function AppShell() {
  const session = useAdminSession();
  const online = useOnline();
  const release = useReleaseFeatures();
  return (
    <div className={styles.layout}>
      <aside className={styles.sidebar} aria-label="管理导航">
        <div className={styles.brand}>
          <span className={styles.mark} aria-hidden="true">CM</span>
          <span>Clothes Model</span>
        </div>
        <nav>
          {GROUPS.map((group, index) => (
            <div key={group.label ?? `group-${index}`}>
              {group.label ? <p className={styles.groupLabel}>{group.label}</p> : null}
              {group.items.filter((item) => !item.feature || release.hasFeature(item.feature)).map((item) => (
                <NavLink
                  key={item.to}
                  className={({ isActive }) => `${styles.navItem} ${isActive ? styles.active : ''}`}
                  to={item.to}
                >
                  {item.label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <p className={styles.scope}>
          <NavLink to="/contract-status">契约状态</NavLink>
        </p>
      </aside>
      <div className={styles.workspace}>
        <header className={styles.topbar}>
          <span>{online ? '后端会话在线' : '后端离线或网络中断'}</span>
          <button type="button" onClick={() => void session.logout()}>退出管理会话</button>
        </header>
        {!online ? (
          <div className={styles.offlineBanner} role="alert">
            后端离线：显示最近一次已知状态，所有写操作已停用，恢复网络后自动重连。
          </div>
        ) : null}
        <Outlet />
      </div>
    </div>
  );
}
