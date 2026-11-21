"""Exercise staging/activation/rollback through cPanel in an isolated public subdirectory."""
import hashlib, json, os, secrets
import deploy_site as D
D.load_env()
cp=D.CPanel(os.environ['BARIK_HOST_SERVER'],os.environ['BARIK_HOST_DOMAIN'],os.environ['BARIK_HOST_USER'],'',os.environ['BARIK_HOST_TOKEN'])
cp.login()
rid=secrets.token_hex(12); token=secrets.token_hex(32)
endpoint='barik-release-'+rid+'.php'; probe='barik-probe-'+rid
source=open(os.path.join(D.HERE,'release_guard.php')).read().replace('__TOKEN__',token).replace('__ID__',rid)
# Use the actual guarded transaction against a dedicated empty test root.
source=source.replace("        release_action(__DIR__,", "        if (($_GET['action'] ?? '') === 'preflight') { $cfg = require __DIR__ . '/api/config.php'; echo json_encode(['ok'=>true,'webhook_secret_present'=>!empty($cfg['DODO_WEBHOOK_SECRET']),'sqlite'=>extension_loaded('pdo_sqlite'),'zip_aes'=>defined('ZipArchive::EM_AES_256')]); exit; }\n        release_action(__DIR__,")
source=source.replace("        release_action(__DIR__,", "        $probe = __DIR__ . '/"+probe+"';\n        if (!is_dir($probe)) { mkdir($probe,0755); file_put_contents($probe . '/app.js','old'); }\n        release_action($probe,")
# Finalize only this probe and the temporary authenticated endpoint.
source=source.replace("        release_action($probe,", "        if (($_GET['action'] ?? '') === 'finalize') { unlink($probe . '/app.js'); if (is_file($probe . '/.htaccess')) unlink($probe . '/.htaccess'); rmdir($probe); unlink(__FILE__); echo '{\"ok\":true}'; exit; }\n        release_action($probe,")
cp.ok(cp.uapi('Fileman','upload_files',files={'file-1':(endpoint,source.encode(),'text/plain')},dir='public_html',overwrite='0'),'probe endpoint')
c={'url':'https://'+os.environ['BARIK_HOST_DOMAIN']+'/'+endpoint,'token':token}
import requests
preflight=requests.post(c['url']+'?action=preflight',headers={'X-Release-Token':token},timeout=30)
preflight.raise_for_status(); flags=preflight.json()
print('HOST_PREFLIGHT',json.dumps(flags))
if not all(flags.get(k) for k in ('ok','webhook_secret_present','sqlite','zip_aes')):
 requests.post(c['url']+'?action=finalize',headers={'X-Release-Token':token},timeout=30)
 raise RuntimeError('Host preflight failed; production deployment must remain blocked')
D.release_control('prepare',c)
root=next(f['absdir'] for f in cp.uapi('Fileman','list_files',dir='public_html')['data'] if f.get('absdir','').endswith('/public_html'))
work=root.rsplit('/',1)[0]+'/barik-release-'+rid
for directory,name,blob in [(work+'/stage','app.js',b'new'),(work,'manifest.json',json.dumps({'app.js':hashlib.sha256(b'new').hexdigest()}).encode())]:
 cp.ok(cp.uapi('Fileman','upload_files',files={'file-1':(name,blob,'text/plain')},dir=directory,overwrite='1'),'probe data')
import requests
try:
 D.release_control('activate',c)
 r=requests.get('https://'+os.environ['BARIK_HOST_DOMAIN']+'/'+probe+'/app.js',timeout=30); r.raise_for_status(); assert r.text=='new'
 D.release_control('rollback',c)
 r=requests.get('https://'+os.environ['BARIK_HOST_DOMAIN']+'/'+probe+'/app.js',timeout=30); r.raise_for_status(); assert r.text=='old'
 print('CPANEL_GUARD_PROBE_OK: activation and rollback verified over HTTPS')
finally:
 D.release_control('finalize',c)
