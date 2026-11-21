"""Inject ZipArchive failures without contacting Telegram or changing project config."""
import os
import pathlib, subprocess, tempfile, unittest, json
LIB=pathlib.Path(__file__).resolve().parents[1]/'server/api/lib.php'
class BackupFailures(unittest.TestCase):
    def test_zip_failures_stop_before_delivery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp); (root/'lib.php').write_bytes(LIB.read_bytes()); (root/'config.php').write_text('<?php return [];'); (root/'db').write_text('snapshot')
            for step in ('password','add','encrypt','close','verify'):
                php='''class ZipArchive {
 const CREATE=1, OVERWRITE=2, EM_AES_256=259;
 function open($p,$flags=0){if($flags)file_put_contents($p,'zip');return true;}
 function setPassword($p){return getenv('FAIL')!=='password';}
 function addFile($p,$n){return getenv('FAIL')!=='add';}
 function setEncryptionName($n,$e){return getenv('FAIL')!=='encrypt';}
 function addFromString($n,$b){return true;}
 function close(){file_put_contents(getenv('CLOSE_LOG'),'closed\\n',FILE_APPEND);return getenv('FAIL')!=='close';}
 function statName($n){return ['encryption_method'=>0];}
}
'''+f'require {json.dumps(str(root/"lib.php"))}; putenv("CLOSE_LOG={tmp}/close-{step}"); putenv("FAIL={step}"); putenv("BARIK_DATA_DIR={tmp}"); var_export(backup_offsite({json.dumps(str(root/"db"))},"pw","owner","2026-11-15"));'
                binary, libs=json.loads(subprocess.check_output(['php','-r','echo json_encode([PHP_BINARY,getenv("LD_LIBRARY_PATH") ?: ""]);']))
                result=subprocess.run([binary,'-n','-r',php],capture_output=True,text=True,env=dict(os.environ,LD_LIBRARY_PATH=libs))
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual(result.stdout,'false',step)
                self.assertTrue((root/f'close-{step}').exists(),step)
                self.assertFalse((root/'backups/barik-db-2026-11-15.zip').exists())
if __name__=='__main__': unittest.main()
