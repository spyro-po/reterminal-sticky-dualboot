#!/usr/bin/env python3
"""Package an audited, committed source-only release locally. Never publishes."""
import io
import json
import subprocess
import zipfile
from common import ROOT,require,sha,write_new
from audit_public import index_files,archive_files


def package():
    require(not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT).strip(),'Commit reviewed source first')
    version=(ROOT/'VERSION').read_text().strip()
    require(version in ('1.0.0','1.1.0'),'Unsupported source release version')
    records=index_files()
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for record in sorted(records,key=lambda r:r['path']):
            data=subprocess.check_output(['git','show',commit+':'+record['path']],cwd=ROOT)
            entry=zipfile.ZipInfo(record['path'],(2000,1,1,0,0,0))
            entry.compress_type=zipfile.ZIP_DEFLATED
            entry.create_system=3
            mode=subprocess.check_output(['git','ls-files','--stage','--',record['path']],cwd=ROOT,text=True).split()[0]
            require(mode in ('100644','100755'),'Unsupported source file mode')
            entry.external_attr=(0o100755 if mode=='100755' else 0o100644)<<16
            archive.writestr(entry,data)
    out=ROOT/'dist'/('v'+version)
    require(not out.exists(),'Release output exists; inspect/remove it manually before repackaging')
    write_new(out/('reterminal-sticky-dualboot-v'+version+'-source.zip'),buf.getvalue())
    archive_files(out/('reterminal-sticky-dualboot-v'+version+'-source.zip'))
    write_new(out/'RELEASE_NOTES.md',(ROOT/'RELEASE_NOTES.md').read_bytes())
    manifest={'version':version,'git_commit':commit,'contents':'source-only',
              'firmware_bins_included':False,'seeedash_included':False,'private_data_included':False,
              'binary_redistribution':'not cleared; excluded','source_files':len(records)}
    write_new(out/'release-manifest.json',(json.dumps(manifest,indent=2)+'\n').encode())
    sums=''.join(sha(p.read_bytes())+'  '+p.name+'\n' for p in sorted(out.iterdir()))
    write_new(out/'SHA256SUMS.txt',sums.encode())
    print('Audited LOCAL source-only release:',out)


if __name__=='__main__':package()
