"""JSON arguments, same catalog as MCP. Images saved as files, not base64 text."""
import argparse
import json
from pathlib import Path
from core import Catalog


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['register_source','list_sources','index_source','create_job','get_job_status','next_batch','get_asset_view','submit_decisions','control_job','search_assets','get_catalog_asset','record_usage','get_usage','commit_to_eagle'])
    parser.add_argument('--args-file',type=Path)
    parser.add_argument('--data',type=Path)
    parser.add_argument('--image-out',type=Path)
    args=parser.parse_args()
    values=json.loads(args.args_file.read_text(encoding='utf-8-sig')) if args.args_file else {}
    if args.command in ('next_batch','get_asset_view','get_catalog_asset') and args.image_out is None:
        parser.error('--image-out is required for image tools')
    result=getattr(Catalog(args.data),args.command)(**values)
    if isinstance(result,tuple):
        result,image=result
        if image:
            args.image_out.write_bytes(image)
            result['image_path']=str(args.image_out.resolve())
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
