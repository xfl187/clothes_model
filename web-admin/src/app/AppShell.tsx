import { NavLink, Outlet } from 'react-router-dom';

import styles from './AppShell.module.css';
import { useAdminSession } from '../features/auth/adminSessionState';

export function AppShell() {
  const session = useAdminSession();
  return (
    <div className={styles.layout}>
      <aside className={styles.sidebar} aria-label="工程验证导航">
        <div className={styles.brand}>
          <span className={styles.mark} aria-hidden="true">CM</span>
          <span>Clothes Model</span>
        </div>
        <p className={styles.groupLabel}>管理</p>
        <nav>
          <NavLink
            className={({ isActive }) => `${styles.navItem} ${isActive ? styles.active : ''}`}
            to="/providers"
          >
            Provider
          </NavLink>
          <NavLink
            className={({ isActive }) => `${styles.navItem} ${isActive ? styles.active : ''}`}
            to="/contract-status"
          >
            契约状态
          </NavLink>
        </nav>
        <p className={styles.scope}>Phase 4<br />最小端到端管理面</p>
      </aside>
      <div className={styles.workspace}>
        <header className={styles.topbar}>
          <span>Clothes Model / 管理控制台</span>
          <button type="button" onClick={() => void session.logout()}>退出登录</button>
        </header>
        <Outlet />
      </div>
    </div>
  );
}
