import { useEffect, useMemo, useState } from 'react';

import type {
  ProviderAdminGateway,
  ProviderConfig,
  ProviderConnectionTestResult,
  ProviderValidationResult,
} from '../../api/adminProviderGateway';
import { OpenApiProviderAdminGateway, providerAdminErrorMessage } from '../../api/adminProviderGateway';
import { useAdminSession } from '../auth/adminSessionState';
import styles from './ProviderAdminPage.module.css';

const ENDPOINT = 'https://ark.cn-beijing.volces.com/api/v3';
const MODEL = 'doubao-seedream-4-5-251128';

function providerStateLabel(state: ProviderConfig['state']) {
  switch (state) {
    case 'inactive': return '未启用';
    case 'validated': return '已验证';
    case 'active': return '已启用';
    case 'disabled': return '已归档';
    default: return '未知状态';
  }
}

export function ProviderAdminPage({ gateway: supplied }: { gateway?: ProviderAdminGateway }) {
  const session = useAdminSession();
  const gateway = useMemo(
    () => supplied ?? new OpenApiProviderAdminGateway(session.session?.csrfToken ?? ''),
    [session.session?.csrfToken, supplied],
  );
  const [items, setItems] = useState<ProviderConfig[]>([]);
  const [selected, setSelected] = useState<ProviderConfig>();
  const [name, setName] = useState('火山方舟 Seedream 4.5');
  const [apiKey, setApiKey] = useState('');
  const [timeout, setTimeoutValue] = useState(120);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [confirming, setConfirming] = useState(false);
  const [archiving, setArchiving] = useState<ProviderConfig>();
  const [deleting, setDeleting] = useState<ProviderConfig>();
  const [validation, setValidation] = useState<ProviderValidationResult>();
  const [connection, setConnection] = useState<ProviderConnectionTestResult>();

  useEffect(() => {
    let active = true;
    void gateway.list().then(
      configs => { if (active) setItems(configs); },
      () => { if (active) setError('无法读取 Provider 配置。'); },
    );
    return () => { active = false; };
  }, [gateway]);

  const run = async (action: () => Promise<void>) => {
    setBusy(true); setError('');
    try {
      await action();
      const configs = await gateway.list();
      setItems(configs);
      setSelected(current => current ? configs.find(item => item.id === current.id) : current);
    }
    catch (caught) { setError(await providerAdminErrorMessage(caught)); }
    finally { setBusy(false); }
  };

  const edit = (provider: ProviderConfig) => {
    setSelected(provider); setName(provider.displayName); setTimeoutValue(provider.timeoutSeconds);
    setApiKey(''); setValidation(undefined); setError('');
  };
  const archived = selected?.state === 'disabled';

  return <main className={`page ${styles.page}`}>
    <p className="eyebrow">Phase 4 / Provider</p>
    <div className={styles.heading}><div><h1>火山方舟图像生成</h1><p>配置、付费验证、启用并设为新任务默认 Provider。</p></div></div>
    {error && !archiving && !deleting && <p role="alert" className={styles.error}>{error}</p>}
    <div className={styles.grid}>
      <section className={styles.panel} aria-labelledby="provider-list-title">
        <h2 id="provider-list-title">已保存配置</h2>
        {items.length === 0 ? <p className={styles.muted}>尚无配置。</p> : items.map(item =>
          <div className={styles.providerRow} key={item.id}>
            <button aria-label={`${item.state === 'disabled' ? '查看' : '编辑'} ${item.displayName}`} className={styles.provider} type="button" onClick={() => edit(item)}>
              <strong>{item.displayName}</strong><span>{providerStateLabel(item.state)} · {item.secretConfigured ? '密钥已保存' : '缺少密钥'}</span>
            </button>
            <div className={styles.rowActions}>
              {item.state === 'disabled' ? <button
                aria-label={`恢复 ${item.displayName}`}
                disabled={busy || item.type === 'comfyui'}
                type="button"
                onClick={() => void run(async () => { await gateway.restore(item.id); })}
              >恢复</button> : <button
                aria-label={`归档 ${item.displayName}`}
                disabled={busy || item.type === 'comfyui'}
                title={item.type === 'comfyui' ? '系统管理的 ComfyUI 配置不能归档' : '归档配置'}
                type="button"
                onClick={() => setArchiving(item)}
              >归档</button>}
              <button
                aria-label={`删除 ${item.displayName}`}
                className={styles.deleteButton}
                disabled={busy || item.type === 'comfyui'}
                title={item.type === 'comfyui' ? '系统管理的 ComfyUI 配置不能删除' : '永久删除配置'}
                type="button"
                onClick={() => setDeleting(item)}
              >删除</button>
            </div>
          </div>)}
        <button type="button" onClick={() => { setSelected(undefined); setApiKey(''); setValidation(undefined); }}>新建配置</button>
      </section>
      <section className={styles.panel} aria-labelledby="provider-form-title">
        <h2 id="provider-form-title">{selected ? archived ? '查看归档配置' : '编辑配置' : '新建配置'}</h2>
        {archived && <p className={styles.archiveNotice}>此 Provider 已归档，仅保留历史关联。恢复后才能修改、验证或再次启用。</p>}
        <form onSubmit={(event) => { event.preventDefault(); void run(async () => {
          const normalizedApiKey = apiKey.trim();
          const saved = await gateway.save({
            displayName: name, type: 'llm_image_edit', adapterType: 'volcengine_ark_seedream',
            endpoint: ENDPOINT, model: MODEL, timeoutSeconds: timeout,
            ...(normalizedApiKey ? { apiKey: normalizedApiKey } : {}), vendorParameters: { prompt_template_version: 'virtual-try-on-v1' },
          }, selected?.id);
          edit(saved);
        }); }}>
          <label>显示名称<input disabled={archived} required value={name} onChange={event => setName(event.target.value)} /></label>
          <label>API 地址<input readOnly value={ENDPOINT} /></label>
          <label>模型<input readOnly value={MODEL} /></label>
          <label>API Key<input disabled={archived} type="password" autoComplete="new-password" value={apiKey} onChange={event => setApiKey(event.target.value)} placeholder={selected?.secretConfigured ? '留空以保留现有密钥' : '仅写入，不会再次显示'} required={!selected?.secretConfigured} /></label>
          <label>超时（秒）<input disabled={archived} type="number" min={1} max={300} value={timeout} onChange={event => setTimeoutValue(Number(event.target.value))} /></label>
          <button disabled={busy || archived} type="submit">保存配置</button>
        </form>
        {selected && !archived && <div className={styles.actions}>
          <button disabled={busy} type="button" onClick={() => void run(async () => { setConnection(await gateway.connectionTest(selected.id)); })}>测试连接（免费）</button>
          <button disabled={busy} type="button" onClick={() => setConfirming(true)}>最小生成测试（付费）</button>
          <button disabled={busy || selected.state === 'inactive'} type="button" onClick={() => void run(async () => { await gateway.enable(selected.id); })}>启用</button>
          <button disabled={busy || selected.state !== 'active'} type="button" onClick={() => void run(async () => { await gateway.setDefault(selected.id); })}>设为默认</button>
        </div>}
        {connection && <section aria-label="连接测试结果" className={styles.validation}><strong>连接测试：{connection.status}</strong><ul>{connection.steps.map(step => <li key={step.key}>{step.key}: {step.status}{step.detail ? ` — ${step.detail}` : ''}</li>)}</ul></section>}
        {validation && <section aria-label="验证结果" className={styles.validation}><strong>验证：{validation.status}</strong><ul>{validation.steps.map(step => <li key={step.key}>{step.key}: {step.status}{step.detail ? ` — ${step.detail}` : ''}</li>)}</ul></section>}
      </section>
    </div>
    {confirming && selected && <div role="dialog" aria-modal="true" aria-labelledby="cost-title" className={styles.dialogBackdrop}><div className={styles.dialog}><h2 id="cost-title">确认一次付费验证</h2><p>验证会向火山方舟提交一组内置合成图片，并产生最多一张图片的费用。输出只用于结构校验，不会保存。</p><div className={styles.actions}><button type="button" onClick={() => setConfirming(false)}>取消</button><button type="button" onClick={() => { setConfirming(false); void run(async () => { setValidation(await gateway.validate(selected.id)); }); }}>确认并验证一次</button></div></div></div>}
    {archiving && <div role="dialog" aria-modal="true" aria-labelledby="archive-title" className={styles.dialogBackdrop}><div className={styles.dialog}><h2 id="archive-title">确认归档配置</h2><p>归档“{archiving.displayName}”后，新任务将不能再选择它，但历史任务、配置修订和已保存密钥会继续保留。当前默认 Provider 必须先切换后才能归档。</p>{error && <p role="alert" className={styles.error}>{error}</p>}<div className={styles.actions}><button disabled={busy} type="button" onClick={() => setArchiving(undefined)}>取消</button><button disabled={busy} type="button" onClick={() => { const target = archiving; void run(async () => { await gateway.archive(target.id); setArchiving(undefined); }); }}>确认归档</button></div></div></div>}
    {deleting && <div role="dialog" aria-modal="true" aria-labelledby="delete-title" className={styles.dialogBackdrop}><div className={styles.dialog}><h2 id="delete-title">确认删除配置</h2><p>将永久删除“{deleting.displayName}”及其密钥和配置修订。默认 Provider、系统管理配置或已有任务引用的配置会被服务端拒绝删除。</p>{error && <p role="alert" className={styles.error}>{error}</p>}<div className={styles.actions}><button disabled={busy} type="button" onClick={() => setDeleting(undefined)}>取消</button><button className={styles.deleteButton} disabled={busy} type="button" onClick={() => { const target = deleting; void run(async () => { await gateway.remove(target.id); if (selected?.id === target.id) setSelected(undefined); setDeleting(undefined); }); }}>永久删除</button></div></div></div>}
  </main>;
}
