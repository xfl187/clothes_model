import { NavLink, Outlet } from 'react-router-dom';

import styles from './AppShell.module.css';

export function AppShell() {
  return (
    <div className={styles.layout}>
      <aside className={styles.sidebar} aria-label="工程验证导航">
        <div className={styles.brand}>
          <span className={styles.mark} aria-hidden="true">CM</span>
          <span>Clothes Model</span>
        </div>
        <p className={styles.groupLabel}>Phase 1</p>
        <nav>
          <NavLink
            className={({ isActive }) => `${styles.navItem} ${isActive ? styles.active : ''}`}
            to="/contract-status"
          >
            契约状态
          </NavLink>
        </nav>
        <p className={styles.scope}>Engineering skeleton<br />非正式管理页面</p>
      </aside>
      <div className={styles.workspace}>
        <header className={styles.topbar}>
          <span>工程基线 / 契约状态</span>
          <span className={styles.snapshot}>Contract mock</span>
        </header>
        <Outlet />
      </div>
    </div>
  );
}
