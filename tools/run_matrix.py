"""Reproducible image-geometry regression with deterministic synthetic inputs.
Run: python tools/run_matrix.py clean|degraded|adversarial|apex
Dependencies: NumPy only. Writes new outputs to --output (defaults qa).
"""
from pathlib import Path
import argparse,json,sys,time,math,platform
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sector_core import fit_ring,detect,signed_delta,VERSION
from tests.fixtures import fixture

def main():
    p=argparse.ArgumentParser();p.add_argument('suite',choices=('clean','degraded','adversarial','apex'));p.add_argument('--output',type=Path,default=Path('qa'));args=p.parse_args()
    rows=[];start=time.perf_counter();suite=args.suite
    if suite=='clean':
        # Predeclared: all accepted; <=1.5 degrees, center error <=0.75 px.
        for radius,aspect in [(26,1.),(43,1.),(43,.8),(43,1.25),(70,1.)]:
            base,t=fixture(angle=0,radius=radius,aspect=aspect,offset=(5,-4))
            fitted=fit_ring(base);ring=fitted.ring if fitted.valid else None
            for angle in np.arange(0,360,5):
                im,t=fixture(angle=float(angle),radius=radius,aspect=aspect,offset=(5,-4))
                d=detect(im,ring) if ring else None
                error=abs(signed_delta(d.image_angle-float(angle))) if d and d.valid else None
                center=math.hypot(ring.cx-t[0],ring.cy-t[1]) if ring else None
                rows.append(dict(radius=radius,aspect=aspect,angle=float(angle),accepted=bool(d and d.valid),error_deg=error,center_error_px=center,
                    passed=bool(d and d.valid and error<=1.5 and center<=.75),reason=d.reason if d else fitted.reason))
    elif suite=='degraded':
        # Predeclared: >=90% accepted overall, accepted error <=3 degrees.
        rng=np.random.default_rng(261113)
        for case in range(240):
            angle=float(rng.uniform(0,360));radius=int(rng.integers(32,76));aspect=float(rng.uniform(.8,1.25))
            offset=(float(rng.uniform(-5,5)),float(rng.uniform(-5,5)))
            brightness=float(rng.uniform(.62,1.05));noise=float(rng.uniform(0,8))
            kw=dict(angle=angle,radius=radius,aspect=aspect,offset=offset,brightness=brightness,noise=noise,damage=bool(case%2),seed=case+1000,width=float(rng.uniform(38,75)))
            im,t=fixture(**kw);f=fit_ring(im);d=detect(im,f.ring) if f.valid else None
            err=abs(signed_delta(d.image_angle-angle)) if d and d.valid else None
            rows.append(dict(case=case,inputs=kw,accepted=bool(d and d.valid),error_deg=err,passed=bool(not(d and d.valid) or err<=3),reason=d.reason if d else f.reason))
    elif suite=='apex':
        # 432 controlled simulations. The original center is a known parameter.
        # Boundary tint contamination may be accepted with a caution label;
        # actual shifted origins may NEVER gain new >3-degree caution readings.
        for radius in (43,55,70):
            base,_=fixture(radius=radius,angle=0)
            f=fit_ring(base)
            if not f.valid:raise RuntimeError('Reference ring did not fit')
            ring=f.ring
            for right,left in ((5,1),(6,2),(7,3)):
                for angle in range(0,360,30):
                    im,_=fixture(radius=radius,angle=angle,edge_artifact=right,
                                 edge_artifact_left=left,pale_edges=False)
                    d=detect(im,ring)
                    error=abs(signed_delta(d.image_angle-angle)) if d.valid else None
                    rows.append(dict(case='tint_contamination',radius=radius,angle=angle,
                        right_artifact=right,left_artifact=left,accepted=d.valid,quality=d.quality,
                        error_deg=error,passed=bool(not d.valid or error<=3.0),reason=d.reason))
            for offset in ((2,0),(3,0),(4,0),(5,0),(0,3),(3,3),(4,4),(-3,3),(-5,0)):
                for angle in range(0,360,30):
                    im,_=fixture(radius=radius,angle=angle,apex_offset=offset)
                    d=detect(im,ring)
                    error=abs(signed_delta(d.image_angle-angle)) if d.valid else None
                    # Pre-existing standard readings have not been recertified;
                    # this regression constrains the NEW caution exception.
                    rows.append(dict(case='true_displaced_origin',radius=radius,angle=angle,
                        offset_px=offset,accepted=d.valid,quality=d.quality,error_deg=error,
                        passed=bool(not d.valid or d.quality!='APEX_CAUTION' or error<=3.0),reason=d.reason))
    else:
        # Deliberate invalid inputs. Every case must reject; no percentage waiver.
        for radius in (26,43,70):
            for angle in (0,45,90,135,180,225,270,315):
                for kind in ('missing_cone','missing_ring','extra_sector','offset_apex','clipped','wide'):
                    kw=dict(radius=radius,angle=angle)
                    if kind in ('missing_cone','missing_ring','extra_sector'):kw[kind]=True
                    if kind=='offset_apex':kw['apex_offset']=(radius*.24,radius*.12)
                    if kind=='wide':kw['width']=150
                    im,t=fixture(**kw)
                    if kind=='clipped':im=im[:,:-int(radius*.5+16)]
                    f=fit_ring(im);d=detect(im,f.ring) if f.valid else None
                    accepted=bool(d and d.valid)
                    rows.append(dict(radius=radius,angle=angle,kind=kind,accepted=accepted,passed=not accepted,reason=d.reason if d else f.reason))
    accepted=[r for r in rows if r['accepted']];errors=[r['error_deg'] for r in rows if r.get('error_deg') is not None]
    summary=dict(suite=suite,version=VERSION,platform=platform.platform(),python=platform.python_version(),numpy=np.__version__,cases=len(rows),accepted=len(accepted),rejected=len(rows)-len(accepted),failed_cases=sum(not r['passed'] for r in rows),max_accepted_error_deg=max(errors) if errors else None,p95_accepted_error_deg=float(np.percentile(errors,95)) if errors else None,elapsed_seconds=time.perf_counter()-start,
                 classification='SYNTHETIC_IMAGE_GEOMETRY_REGRESSION')
    summary['caution_accepted']=sum(r.get('quality')=='APEX_CAUTION' for r in accepted)
    if suite=='apex':
        tinted=[r for r in rows if r['case']=='tint_contamination']
        tinted_accepted=sum(r['accepted'] for r in tinted)
        summary['tinted_accepted']=tinted_accepted
        summary['tinted_total']=len(tinted)
        summary['pass']=summary['failed_cases']==0 and tinted_accepted>=.60*len(tinted) and summary['caution_accepted']>=10
    else:
        summary['pass']=summary['failed_cases']==0 and (suite!='degraded' or len(accepted)>=.9*len(rows))
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/(suite+'_results.json')).write_text(json.dumps(dict(summary=summary,rows=rows),indent=2,allow_nan=False))
    print(json.dumps(summary,indent=2));print('Failures', [r for r in rows if not r['passed']][:12])
    return 0 if summary['pass'] else 1

if __name__=='__main__':raise SystemExit(main())
