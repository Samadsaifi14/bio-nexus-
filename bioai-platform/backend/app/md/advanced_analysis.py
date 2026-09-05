"""Advanced trajectory analysis for BioNexus MD.

The functions operate on Cartesian coordinate frames (frames x atoms x 3) and
return deterministic, serialisable scientific outputs. Coordinates are aligned
to the first frame by the Kabsch algorithm before fluctuation/correlation/PCA
analyses. No value is labelled as SASA or hydrogen bonding unless the required
atom radii/topology indices are supplied by the caller.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np


def _frames(value: Any) -> np.ndarray:
    xyz=np.asarray(value,dtype=float)
    if xyz.ndim!=3 or xyz.shape[2]!=3 or xyz.shape[0]<1 or xyz.shape[1]<1:
        raise ValueError("coordinates must have shape [frames, atoms, 3]")
    if not np.isfinite(xyz).all(): raise ValueError("coordinates contain non-finite values")
    return xyz


def _kabsch(mobile:np.ndarray,reference:np.ndarray)->np.ndarray:
    m=mobile-mobile.mean(axis=0); r=reference-reference.mean(axis=0)
    h=m.T@r; u,s,vt=np.linalg.svd(h); d=np.linalg.det(vt.T@u.T)
    correction=np.eye(3); correction[2,2]=-1.0 if d<0 else 1.0
    rot=vt.T@correction@u.T
    return m@rot+reference.mean(axis=0)


def align_trajectory(coordinates:Any)->np.ndarray:
    xyz=_frames(coordinates); ref=xyz[0]
    return np.stack([_kabsch(frame,ref) for frame in xyz],axis=0)


def rmsd_series(aligned:np.ndarray)->list[float]:
    ref=aligned[0]
    return np.sqrt(np.mean(np.sum((aligned-ref)**2,axis=2),axis=1)).tolist()


def rmsf_series(aligned:np.ndarray)->list[float]:
    mean=aligned.mean(axis=0)
    return np.sqrt(np.mean(np.sum((aligned-mean)**2,axis=2),axis=0)).tolist()


def radius_of_gyration(aligned:np.ndarray,masses:list[float]|None=None)->list[float]:
    n=aligned.shape[1]
    w=np.asarray(masses if masses is not None else np.ones(n),dtype=float)
    if w.shape!=(n,) or (w<=0).any(): raise ValueError("masses must contain one positive value per atom")
    w=w/w.sum(); out=[]
    for frame in aligned:
        center=(frame*w[:,None]).sum(axis=0)
        out.append(float(math.sqrt(float((w*np.sum((frame-center)**2,axis=1)).sum()))))
    return out


def contact_map(aligned:np.ndarray,cutoff:float=8.0)->dict:
    if cutoff<=0: raise ValueError("contact cutoff must be positive")
    n=aligned.shape[1]; counts=np.zeros((n,n),dtype=float)
    for frame in aligned:
        diff=frame[:,None,:]-frame[None,:,:]; dist=np.sqrt(np.sum(diff*diff,axis=2)); counts+=(dist<=cutoff)
    freq=counts/aligned.shape[0]; np.fill_diagonal(freq,0.0)
    return {"method":"heavy-atom distance contact frequency","cutoff_angstrom":cutoff,"matrix":freq.tolist()}


def dccm(aligned:np.ndarray)->dict:
    disp=aligned-aligned.mean(axis=0,keepdims=True); n=aligned.shape[1]
    matrix=np.zeros((n,n),dtype=float)
    norms=np.sqrt(np.mean(np.sum(disp*disp,axis=2),axis=0))
    for i in range(n):
        for j in range(i,n):
            denom=norms[i]*norms[j]
            value=0.0 if denom==0 else float(np.mean(np.sum(disp[:,i,:]*disp[:,j,:],axis=1))/denom)
            value=max(-1.0,min(1.0,value)); matrix[i,j]=matrix[j,i]=value
    return {"method":"dynamic cross-correlation of aligned Cartesian fluctuations","matrix":matrix.tolist(),"atoms":n,"frames":aligned.shape[0]}


def pca(aligned:np.ndarray,components:int=3)->dict:
    x=aligned.reshape(aligned.shape[0],-1); x=x-x.mean(axis=0,keepdims=True)
    if aligned.shape[0]<2:
        return {"method":"Cartesian PCA","components":[],"eigenvalues":[],"explained_variance_ratio":[],"scores":[]}
    cov=np.cov(x,rowvar=False); vals,vecs=np.linalg.eigh(cov); order=np.argsort(vals)[::-1]; vals=vals[order]; vecs=vecs[:,order]
    k=max(1,min(int(components),len(vals))); vals_k=np.maximum(vals[:k],0); total=float(np.maximum(vals,0).sum()); scores=x@vecs[:,:k]
    return {"method":"PCA of Kabsch-aligned Cartesian coordinates","components":k,"eigenvalues":vals_k.tolist(),"explained_variance_ratio":((vals_k/total) if total>0 else np.zeros(k)).tolist(),"scores":scores.tolist()}


def free_energy_landscape(scores:list[list[float]],temperature_k:float=300.0,bins:int=30)->dict:
    arr=np.asarray(scores,dtype=float)
    if arr.ndim!=2 or arr.shape[0]<2 or arr.shape[1]<2:
        return {"method":"Boltzmann free-energy landscape over PC1/PC2","available":False,"reason":"at least two frames and two PCA dimensions required"}
    bins=max(5,min(100,int(bins))); hist,xedges,yedges=np.histogram2d(arr[:,0],arr[:,1],bins=bins); prob=hist/hist.sum() if hist.sum() else hist
    kb=0.00831446261815324 # kJ mol^-1 K^-1
    with np.errstate(divide="ignore"): fe=-kb*float(temperature_k)*np.log(prob)
    finite=np.isfinite(fe)
    if finite.any(): fe[finite]-=fe[finite].min()
    grid=[[None if not math.isfinite(float(v)) else float(v) for v in row] for row in fe]
    return {"method":"-RT ln(P) on PCA histogram","available":True,"temperature_k":temperature_k,"energy_unit":"kJ/mol","bins":bins,"pc1_edges":xedges.tolist(),"pc2_edges":yedges.tolist(),"free_energy":grid}


def _sphere_points(n:int)->np.ndarray:
    pts=[]; phi=math.pi*(3-math.sqrt(5))
    for i in range(n):
        y=1-(i/(n-1))*2 if n>1 else 0; radius=math.sqrt(max(0,1-y*y)); theta=phi*i
        pts.append((math.cos(theta)*radius,y,math.sin(theta)*radius))
    return np.asarray(pts,dtype=float)


def sasa_series(aligned:np.ndarray,atom_radii:list[float],probe_radius:float=1.4,sphere_points:int=96)->dict:
    n=aligned.shape[1]; radii=np.asarray(atom_radii,dtype=float)
    if radii.shape!=(n,) or (radii<=0).any(): raise ValueError("atom_radii must contain one positive radius per atom")
    points=_sphere_points(max(24,min(960,int(sphere_points)))); expanded=radii+probe_radius; areas=[]
    for frame in aligned:
        total=0.0
        for i in range(n):
            test=frame[i]+points*expanded[i]; accessible=np.ones(len(points),dtype=bool)
            for j in range(n):
                if i==j: continue
                accessible &= np.sum((test-frame[j])**2,axis=1) > expanded[j]**2
                if not accessible.any(): break
            total += 4*math.pi*expanded[i]**2*float(accessible.mean())
        areas.append(total)
    return {"method":"Shrake-Rupley","probe_radius_angstrom":probe_radius,"sphere_points_per_atom":len(points),"unit":"angstrom^2","series":areas}


def hydrogen_bond_series(aligned:np.ndarray,triples:list[list[int]],distance_cutoff:float=3.5,angle_cutoff_deg:float=120.0)->dict:
    n=aligned.shape[1]; clean=[]
    for triple in triples:
        if len(triple)!=3: raise ValueError("hydrogen bond topology entries must be [donor, hydrogen, acceptor]")
        d,h,a=map(int,triple)
        if min(d,h,a)<0 or max(d,h,a)>=n: raise ValueError("hydrogen bond topology index out of range")
        clean.append((d,h,a))
    counts=[]
    for frame in aligned:
        count=0
        for d,h,a in clean:
            ha=float(np.linalg.norm(frame[h]-frame[a])); v1=frame[d]-frame[h]; v2=frame[a]-frame[h]; denom=np.linalg.norm(v1)*np.linalg.norm(v2)
            angle=0.0 if denom==0 else math.degrees(math.acos(float(np.clip(np.dot(v1,v2)/denom,-1,1))))
            if ha<=distance_cutoff and angle>=angle_cutoff_deg: count+=1
        counts.append(count)
    return {"method":"geometric donor-H-acceptor hydrogen bonds","distance_cutoff_angstrom":distance_cutoff,"angle_cutoff_deg":angle_cutoff_deg,"candidate_triplets":len(clean),"series":counts}


def trajectory_animation(aligned:np.ndarray,max_frames:int=100)->dict:
    step=max(1,math.ceil(aligned.shape[0]/max(1,int(max_frames)))); indices=list(range(0,aligned.shape[0],step))
    return {"format":"coordinate-keyframes","frame_indices":indices,"coordinates":aligned[indices].tolist(),"note":"client may animate these aligned Cartesian keyframes; this is not a rendered movie file"}


def analyze_trajectory(coordinates:Any,*,masses:list[float]|None=None,atom_radii:list[float]|None=None,hydrogen_bond_triples:list[list[int]]|None=None,secondary_structure_timeline:list[Any]|None=None,contact_cutoff:float=8.0,temperature_k:float=300.0,pca_components:int=3,free_energy_bins:int=30)->dict:
    aligned=align_trajectory(coordinates); pca_result=pca(aligned,pca_components)
    result={
      "frames":int(aligned.shape[0]),"atoms":int(aligned.shape[1]),"alignment":{"method":"Kabsch","reference_frame":0},
      "rmsd":{"unit":"angstrom","series":rmsd_series(aligned)},
      "rmsf":{"unit":"angstrom","per_atom":rmsf_series(aligned)},
      "radius_of_gyration":{"unit":"angstrom","series":radius_of_gyration(aligned,masses)},
      "contact_map":contact_map(aligned,contact_cutoff),"dccm":dccm(aligned),"pca":pca_result,
      "free_energy_landscape":free_energy_landscape(pca_result.get("scores") or [],temperature_k,free_energy_bins),
      "trajectory_animation":trajectory_animation(aligned),
    }
    result["sasa"] = sasa_series(aligned,atom_radii) if atom_radii is not None else {"available":False,"reason":"atom radii/topology were not supplied; BioNexus will not fabricate SASA"}
    result["hydrogen_bonds"] = hydrogen_bond_series(aligned,hydrogen_bond_triples) if hydrogen_bond_triples is not None else {"available":False,"reason":"donor/hydrogen/acceptor topology was not supplied"}
    result["secondary_structure_timeline"] = {"available":secondary_structure_timeline is not None,"source":"caller/topology-aware DSSP assignment" if secondary_structure_timeline is not None else None,"timeline":secondary_structure_timeline or [],"reason":None if secondary_structure_timeline is not None else "secondary structure requires topology-aware assignment; coordinates alone are insufficient"}
    return result
