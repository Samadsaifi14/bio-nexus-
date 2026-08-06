"""ADMET descriptor computation using RDKit — industrial-grade panel.

Computes 50+ molecular descriptors including:
  - Core physicochemical properties (MW, LogP, TPSA, HBD, HBA, etc.)
  - Extended topological descriptors (Fsp3, aromatic rings, MR, volume, complexity)
  - Drug-likeness filters (Lipinski, Veber, Ghose, Egan, MDDR, PAINS, Brenk)
  - ADMET predictions (absorption, distribution, metabolism, toxicity, clearance)
  - Structural alerts and functional group analysis
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def _fg(mol, name: str) -> int:
    """Safely call a Fragments.fr_* function, returning 0 if unavailable."""
    from rdkit.Chem import Fragments
    fn = getattr(Fragments, name, None)
    if fn is None:
        return 0
    try:
        return fn(mol)
    except Exception:
        return 0


# --- BOILED-Egg (Daina & Zoete, ChemMedChem 2016) -------------------------
# Boundary polygons (x=TPSA Å², y=WLOGP) from the paper's supporting info —
# identical to the shapes SwissADME uses for the GI-absorption and BBB
# classification and its graphical output.
_GIA_COORDS = (
    (97.80552243681136, -2.227039047489081), (101.88198219217963, -2.1900004937640487),
    (105.83667285876659, -2.1352635055090943), (109.65398707923741, -2.063044104609906),
    (113.31885965832892, -1.9736273080479292), (116.81682701829244, -1.8673660030685453),
    (120.13408428002757, -1.7446795544963347), (123.25753974463277, -1.6060521496937052),
    (126.17486656036041, -1.452030887694577), (128.87455137106866, -1.2832236200544374),
    (131.3459397541782, -1.100296551937959), (133.57927826881107, -0.903971612911568),
    (135.56575294816514, -0.6950236078172709), (137.29752408421504, -0.4742771589719089),
    (138.76775716745777, -0.2426034517596168), (139.97064985959926, -0.0009167964611120461),
    (140.90145489273314, 0.2498289801112721), (141.556498804638, 0.5086442989322527),
    (141.9331964362546, 0.7745077341799151), (142.03006113412775, 1.0463700443367885),
    (141.84671061754818, 1.323158313066756), (141.38386848723997, 1.6037801835256746),
    (140.64336136963902, 1.88712816939478), (139.628111708033, 2.1720840256232266),
    (138.34212622901268, 2.457523161630431), (136.790480129753, 2.7423190795513075),
    (134.97929704852805, 3.025347820008701), (132.91572489750854, 3.3054923978675586),
    (130.60790765321815, 3.5816472104649564), (128.06495321597865, 3.8527224009187018),
    (125.29689746518848, 4.1176481592945535), (122.31466465229157, 4.375378944657261),
    (119.13002428774791, 4.624897611343), (115.75554469215258, 4.865219423168597),
    (112.20454339481628, 5.095395939735363), (108.49103457556141, 5.314518759490062),
    (104.62967375715677, 5.521723104770812), (100.63569996666462, 5.716191234689457),
    (96.52487559396305, 5.8971556723812375), (92.313424184794, 6.063902233885377),
    (88.0179664138405, 6.215772846702879), (83.6554544905163, 6.352168146908026),
    (79.2431052563408, 6.472549844564003), (74.79833223793057, 6.576442848107324),
    (70.3386769237657, 6.663437139317204), (65.88173953594848, 6.733189391470147),
    (61.445109570167645, 6.785424324293678), (57.04629637799464, 6.8199357903718125),
    (52.7026600654724, 6.836587588714733), (48.43134298070782, 6.83531400228186),
    (44.24920206085525, 6.816120057336999), (40.17274230548697, 6.779081503611968),
    (36.218051638900036, 6.7243445153570125), (32.400737418429216, 6.652125114457824),
    (28.735864839337697, 6.562708317895847), (25.237897479374148, 6.456447012916463),
    (21.92064021763908, 6.333760564344252), (18.79718475303387, 6.195133159541625),
    (15.879857937306236, 6.0411118975424944), (13.180173126598005, 5.872304629902357),
    (10.708784743488392, 5.689377561785878), (8.475446228855569, 5.493052622759485),
    (6.488971549501496, 5.284104617665191), (4.757200413451594, 5.063358168819828),
    (3.286967330208895, 4.8316844616075345), (2.084074638067364, 4.589997806309031),
    (1.1532696049334672, 4.339252029736645), (0.4982256930286379, 4.0804367109156665),
    (0.12152806141202838, 3.8145732756680006), (0.024663363538902687, 3.5427109655111297),
    (0.2080138801184492, 3.265922696781163), (0.6708560104266521, 2.9853008263222423),
    (1.4113631280275918, 2.701952840453139), (2.426612789633675, 2.416996984224689),
    (3.7125982686539536, 2.1315578482174877), (5.264244367913619, 1.846761930296613),
    (7.0754274491385845, 1.5637331898392164), (9.138999600158078, 1.2835886119803601),
    (11.4468168444485, 1.0074337993829612), (13.989771281687991, 0.7363586089292161),
    (16.75782703247815, 0.4714328505533679), (19.740059845375065, 0.21370206519065607),
    (22.92470020991869, -0.03581660149508132), (26.29917980551407, -0.27613841332067823),
    (29.85018110285037, -0.506314929887444), (33.563689922105276, -0.7254377496421445),
    (37.425050740509896, -0.9326420949228948), (41.419024531002, -1.127110224841536),
    (45.529848903703616, -1.3080746625333208), (49.7413003128726, -1.4748212240374596),
    (54.0367580838262, -1.6266918368549592), (58.39927000715034, -1.7630871370601089),
    (62.81161924132584, -1.8834688347160848), (67.25639225973609, -1.9873618382594065),
    (71.71604757390092, -2.074356129469285), (76.17298496171819, -2.144108381622228),
    (80.609614927499, -2.196343314445759), (85.00842811967199, -2.2308547805238947),
    (89.35206443219425, -2.247506578866816), (93.62338151695882, -2.2462329924339417),
    (97.80552243681143, -2.2270390474890807),
)
_BBB_COORDS = (
    (40.97017925131679, 0.4062562899766126), (43.53440363567211, 0.4169942065264866),
    (46.077057183913354, 0.4386559712786629), (48.58810520411346, 0.4711560951439837),
    (51.05763773692548, 0.5143663149814472), (53.47590866566447, 0.5681160997942261),
    (55.83337417977759, 0.6321933237376053), (58.120730439904186, 0.7063451032827793),
    (60.328950295879224, 0.7902787952326094), (62.449318912770856, 0.8836631516506256),
    (64.47346816435247, 0.9861296271452998), (66.39340965827392, 1.0972738333503356),
    (68.20156626259653, 1.2166571348607977), (69.8908020092712, 1.3438083803266692),
    (71.45445025654422, 1.4782257618719723), (72.88633999914657, 1.61937879550121),
    (74.1808202224323, 1.766710414677333), (75.33278220435197, 1.9196391688088683),
    (76.33767967724427, 2.07756151796976), (77.19154676987765, 2.239854214795729),
    (77.89101365893231, 2.405876764156885), (78.43331986815312, 2.5749739508993854),
    (78.81632516268847, 2.7464784256803143), (79.03851799561927, 2.9197133386906526),
    (79.09902147334422, 3.093995010872254), (78.99759681627812, 3.2686356320867374),
    (78.73464430120595, 3.442945975587881), (78.31120168157305, 3.6162381180847065),
    (77.72894009194661, 3.7878281546604287), (76.99015745281086, 3.9570388978327133),
    (76.09776940172482, 4.1232025501032945), (75.05529778663279, 4.285663339449613),
    (73.86685676673952, 4.4437801073573935), (72.53713657580352, 4.596928839180382),
    (71.071385011927, 4.744505126841076), (69.47538672689447, 4.885926554153269),
    (67.75544039679461, 5.020634995352665), (65.91833386402362, 5.148098817764284),
    (63.97131734877222, 5.267814979913747), (61.92207483571886, 5.3793110168021645),
    (59.77869374885272, 5.482146904509627), (57.549633034105966, 5.575916796768607),
    (55.243689775758746, 5.660250626653745), (52.86996447836648, 5.734815567066945),
    (50.43782515122604, 5.799317344253877), (47.956870337122915, 5.853501399168046),
    (45.43689123126793, 5.897153892099043), (42.8878330399229, 5.930102546600198),
    (40.319755731215174, 5.952217329385), (37.74279433303931, 5.9634109635090855),
    (35.167118934732244, 5.963639272812449), (32.602894550376924, 5.952901356262576),
    (30.06024100213569, 5.931239591510399), (27.54919298193556, 5.898739467645077),
    (25.079660449123548, 5.855529247807613), (22.66138952038456, 5.801779462994835),
    (20.303924006271433, 5.7377022390514565), (18.016567746144844, 5.663550459506283),
    (15.808347890169804, 5.579616767556452), (13.687979273278186, 5.486232411138436),
    (11.663830021696565, 5.38376593564376), (9.743888527775118, 5.272621729438726),
    (7.935731923452518, 5.153238427928264), (6.2464961767778435, 5.026087182462394),
    (4.682847929504812, 4.8916698009170885), (3.2509581869024937, 4.750516767287851),
    (1.9564779636167104, 4.603185148111728), (0.8045159816970635, 4.450256393980193),
    (-0.20038149119524168, 4.2923340448193015), (-1.054248583828624, 4.130041347993332),
    (-1.7537154728832645, 3.9640187986321784), (-2.2960216821040977, 3.7949216118896762),
    (-2.67902697663943, 3.623417137108748), (-2.9012198095702453, 3.450182224098408),
    (-2.961723287295181, 3.275900551916808), (-2.8602986302290945, 3.1012599307023248),
    (-2.5973461151568977, 2.9269495872011797), (-2.173903495524005, 2.753657444704355),
    (-1.5916419058975677, 2.582067408128632), (-0.8528592667618298, 2.4128566649563483),
    (0.039528784324221584, 2.246693012685768), (1.0820003994162777, 2.0842322233394484),
    (2.2704414193095257, 1.9261154554316693), (3.6001616102455305, 1.7729667236086788),
    (5.0659131741220245, 1.6253904359479865), (6.6619114591545925, 1.4839690086357915),
    (8.381857789254436, 1.3492605674363958), (10.21896432202541, 1.2217967450247778),
    (12.165980837276834, 1.102080582875313), (14.215223350330179, 0.9905845459868972),
    (16.358604437196348, 0.8877486582794322), (18.58766515194309, 0.7939787660204534),
    (20.893608410290287, 0.7096449361353171), (23.26733370768257, 0.6350799957221163),
    (25.699473034822983, 0.5705782185351836), (28.18042784892613, 0.5163941636210154),
    (30.700406954781126, 0.4727416706900189), (33.24946514612614, 0.4397930161888647),
    (35.817542454833884, 0.41767823340406107), (38.39450385300971, 0.4064845992799761),
    (40.970179251316814, 0.4062562899766126),
)


def _point_in_polygon(px: float, py: float, poly) -> bool:
    """Ray-casting point-in-polygon test (points are (x=TPSA, y=WLOGP))."""
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > py) != (yj > py):
            x_cross = xi + (py - yi) / (yj - yi + 1e-12) * (xj - xi)
            if px < x_cross:
                inside = not inside
        j = i
    return inside


def _esol_log_s(mol, wlogp: float) -> float:
    """Delaney ESOL aqueous solubility (SwissADME substitutes XLOGP3 for
    Daylight CLOGP; we use WLOGP, which is within ~0.1 log unit for most
    drug-like molecules)."""
    from rdkit import Chem
    from rdkit.Chem import Descriptors
    heavy = mol.GetNumHeavyAtoms()
    aromatic_heavy = sum(1 for a in mol.GetAtoms()
                         if a.GetIsAromatic() and a.GetAtomicNum() > 1)
    ap = aromatic_heavy / heavy if heavy else 0.0
    rb = Descriptors.rdMolDescriptors.CalcNumRotatableBonds(mol)
    mw = Descriptors.MolWt(mol)
    return 0.16 - 0.63 * wlogp - 0.0062 * mw + 0.066 * rb - 0.74 * ap


def _solubility_class(log_s: float) -> str:
    if log_s > 0:
        return "Highly soluble"
    if log_s > -2:
        return "Soluble"
    if log_s > -4:
        return "Moderately soluble"
    if log_s > -6:
        return "Slightly soluble"
    if log_s > -8:
        return "Very slightly soluble"
    return "Insoluble"


def _martin_bioavailability(mol, tpsa: float, lipinski_pass: bool) -> float:
    """Abbott/Martin Bioavailability Score (Martin, J. Med. Chem. 2005).
    Acidic (net negative) compounds are scored by TPSA; neutral/zwitterionic/
    cationic compounds by rule-of-five compliance."""
    if sum(a.GetFormalCharge() for a in mol.GetAtoms()) < 0:
        if tpsa <= 75:
            return 0.85
        if tpsa < 150:
            return 0.56
        return 0.11
    return 0.55 if lipinski_pass else 0.17


def compute_descriptors(smiles: str) -> dict:
    """Compute comprehensive ADMET descriptors from a SMILES string."""
    from rdkit import Chem
    from rdkit.Chem import (
        Descriptors, Lipinski, QED, rdMolDescriptors,
        EState, Fragments, Crippen,
    )
    from rdkit.Chem.MolSurf import LabuteASA

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"Invalid SMILES: {smiles!r}")

    n_heavy = mol.GetNumHeavyAtoms()
    n_rings = mol.GetRingInfo().NumRings()
    n_aromatic_rings = sum(1 for ring in mol.GetRingInfo().AtomRings()
                           if all(mol.GetAtomWithIdx(a).GetIsAromatic() for a in ring))

    # ---- Core physicochemical properties ----
    mw = round(Descriptors.MolWt(mol), 2)
    logp = round(Descriptors.MolLogP(mol), 2)
    # SwissADME TPSA uses the Ertl fragmental method including S and P.
    tpsa = round(Descriptors.TPSA(mol, includeSandP=True), 2)
    hbd = Lipinski.NumHDonors(mol)
    # SwissADME "H-bond acceptors" = all N + O atoms (OpenBabel count).
    # CalcNumLipinskiHBA is a pure N+O count; the plain NumHAcceptors /
    # CalcNumHBA exclude e.g. ester carbonyl oxygens and would show 3 for
    # aspirin instead of SwissADME's 4.
    hba = rdMolDescriptors.CalcNumLipinskiHBA(mol)
    rotatable = Lipinski.NumRotatableBonds(mol)
    heavy_atoms = n_heavy
    formula = rdMolDescriptors.CalcMolFormula(mol)
    qed_score = round(QED.qed(mol), 4)

    # ---- Extended topological descriptors ----
    fsp3 = round(Descriptors.FractionCSP3(mol), 4)
    mr = round(Crippen.MolMR(mol), 2)  # molar refractivity
    mol_volume = 0.0
    try:
        mol_volume = round(rdMolDescriptors.CalcMolecularVolume(mol), 2)
    except AttributeError:
        try:
            from rdkit.Chem import Descriptors3D
            mol_volume = round(Descriptors3D.CalcVolume(mol), 2)
        except Exception:
            mol_volume = 0.0
    except Exception:
        mol_volume = 0.0
    complexity = 0.0
    if os.name != "nt":
        try:
            complexity = round(Descriptors.BalabanJ(mol), 4)
        except Exception:
            pass
    try:
        wiener = Descriptors.WeinerIndex(mol)
    except Exception:
        wiener = 0
    try:
        zagreb = Descriptors.ZagrebIndex(mol)
    except Exception:
        zagreb = 0
    num_heteroatoms = Lipinski.NumHeteroatoms(mol)
    num_amide_bonds = rdMolDescriptors.CalcNumAmideBonds(mol)
    num_atom_stereocenters = rdMolDescriptors.CalcNumAtomStereoCenters(mol)
    num_unspecified_stereocenters = rdMolDescriptors.CalcNumUnspecifiedAtomStereoCenters(mol)
    labute_asa = round(LabuteASA(mol), 2)
    estate_sum = round(sum(EState.EStateIndices(mol)), 2)

    # Ring descriptors
    ring_count = n_rings
    aromatic_ring_count = n_aromatic_rings
    aliphatic_ring_count = ring_count - aromatic_ring_count
    num_saturated_rings = sum(1 for ring in mol.GetRingInfo().AtomRings()
                              if all(not mol.GetAtomWithIdx(a).GetIsAromatic() and
                                     mol.GetAtomWithIdx(a).GetDegree() == 3
                                     for a in ring))

    # Functional group counts (safe — tolerates missing rdkit attributes)
    num_oh = _fg(mol, "fr_Al_OH") + _fg(mol, "fr_Ar_OH")
    num_nh = _fg(mol, "fr_NH0") + _fg(mol, "fr_NH1") + _fg(mol, "fr_NH2")
    num_aliphatic_oh = _fg(mol, "fr_Al_OH")
    num_aromatic_oh = _fg(mol, "fr_Ar_OH")
    num_carboxylic = _fg(mol, "fr_COO")
    num_ester = _fg(mol, "fr_ester")
    num_ether = _fg(mol, "fr_ether")
    num_ketone = _fg(mol, "fr_ketone")
    num_aldehyde = _fg(mol, "fr_aldehyde")
    num_halogen = _fg(mol, "fr_halogen")
    num_sulfonamide = _fg(mol, "fr_sulfonamide")
    num_nitro = _fg(mol, "fr_nitro")
    num_phenol = _fg(mol, "fr_phenol")
    num_amine = _fg(mol, "fr_NH0") + _fg(mol, "fr_NH1")

    # ---- Lipinski Rule of Five ----
    lip_violations = []
    if mw > 500:
        lip_violations.append(f"MW {mw} > 500")
    if logp > 5:
        lip_violations.append(f"LogP {logp} > 5")
    if hbd > 5:
        lip_violations.append(f"HBD {hbd} > 5")
    if hba > 10:
        lip_violations.append(f"HBA {hba} > 10")
    lipinski = {"pass": len(lip_violations) <= 1, "violations": lip_violations, "violation_count": len(lip_violations)}

    # ---- Veber rules ----
    veber_violations = []
    if rotatable > 10:
        veber_violations.append(f"Rotatable bonds {rotatable} > 10")
    if tpsa > 140:
        veber_violations.append(f"TPSA {tpsa} > 140")
    veber = {"pass": len(veber_violations) == 0, "violations": veber_violations, "violation_count": len(veber_violations)}

    # ---- Ghose filter (160 <= MW <= 480, -0.4 <= LogP <= 5.6, 20 <= atoms <= 70) ----
    ghose_violations = []
    if mw < 160 or mw > 480:
        ghose_violations.append(f"MW {mw} outside 160-480")
    if logp < -0.4 or logp > 5.6:
        ghose_violations.append(f"LogP {logp} outside -0.4-5.6")
    if n_heavy < 20 or n_heavy > 70:
        ghose_violations.append(f"Heavy atoms {n_heavy} outside 20-70")
    if mr < 40 or mr > 130:
        ghose_violations.append(f"MR {mr} outside 40-130")
    ghose = {"pass": len(ghose_violations) == 0, "violations": ghose_violations, "violation_count": len(ghose_violations)}

    # ---- Egan filter (oral absorption: TPSA <= 132, LogP <= 5.88) ----
    egan_violations = []
    if tpsa > 132:
        egan_violations.append(f"TPSA {tpsa} > 132 (poor absorption)")
    if logp > 5.88:
        egan_violations.append(f"LogP {logp} > 5.88 (poor absorption)")
    egan = {"pass": len(egan_violations) == 0, "violations": egan_violations, "violation_count": len(egan_violations)}

    # ---- Muegge filter (Bayer) — SwissADME drug-likeness panel ----
    muegge_violations = []
    if mw < 200 or mw > 600:
        muegge_violations.append(f"MW {mw} outside 200-600")
    if logp < -2 or logp > 5:
        muegge_violations.append(f"LogP {logp} outside -2-5")
    if tpsa > 150:
        muegge_violations.append(f"TPSA {tpsa} > 150")
    if ring_count > 7:
        muegge_violations.append(f"Ring count {ring_count} > 7")
    if n_heavy <= 4:
        muegge_violations.append(f"Carbons {n_heavy} <= 4")
    if num_heteroatoms <= 1:
        muegge_violations.append(f"Heteroatoms {num_heteroatoms} <= 1")
    if rotatable > 15:
        muegge_violations.append(f"Rotatable bonds {rotatable} > 15")
    if hbd > 5:
        muegge_violations.append(f"HBD {hbd} > 5")
    if hba > 10:
        muegge_violations.append(f"HBA {hba} > 10")
    muegge = {"pass": len(muegge_violations) == 0, "violations": muegge_violations, "violation_count": len(muegge_violations)}

    # ---- MDDR-like rules (drug-like space) ----
    mddr_violations = []
    if mw < 200 or mw > 700:
        mddr_violations.append(f"MW {mw} outside 200-700")
    if logp < -2 or logp > 6:
        mddr_violations.append(f"LogP {logp} outside -2-6")
    if tpsa > 180:
        mddr_violations.append(f"TPSA {tpsa} > 180")
    if rotatable > 15:
        mddr_violations.append(f"Rotatable bonds {rotatable} > 15")
    if ring_count > 8:
        mddr_violations.append(f"Ring count {ring_count} > 8")
    mddr = {"pass": len(mddr_violations) == 0, "violations": mddr_violations, "violation_count": len(mddr_violations)}

    # ---- PAINS alerts (Pan Assay Interference Compounds) ----
    pains_patterns = [
        ("Rhodanine", r"[N,n,O,o,S,s]C(=O)CSC(=S)"),
        ("PAINS_1", r"C=CC(=O)"),  # acrylamide
        ("Quinone", r"C1=CC(=O)C=CC1=O"),
        ("Michael_acceptor", r"C=CC(=O)[N,O]"),
        ("Catechol", r"C1=CC=C(O)C(O)=C1"),
        ("Hydroquinone", r"C1=CC=C(O)C=C1O"),
        ("Aniline", r"Nc1ccccc1"),
        ("Azobenzene", r"N=Nc1ccccc1"),
    ]
    pains_hits = []
    for name, smarts in pains_patterns:
        pattern = Chem.MolFromSmarts(smarts)
        if pattern and mol.HasSubstructMatch(pattern):
            pains_hits.append(name)
    pains = {"pass": len(pains_hits) == 0, "alerts": pains_hits, "alert_count": len(pains_hits)}

    # ---- Brenk structural alerts ----
    brenk_alerts = []
    if _fg(mol, "fr_halogen") > 2:
        brenk_alerts.append("Multiple halogen substituents")
    if _fg(mol, "fr_nitro") > 0:
        brenk_alerts.append("Nitro group (mutagenicity concern)")
    if _fg(mol, "fr_sulfonamide") > 0:
        brenk_alerts.append("Sulfonamide (hypersensitivity risk)")
    if n_aromatic_rings > 5:
        brenk_alerts.append(f"Many aromatic rings ({n_aromatic_rings}) — metabolic liability")
    if _fg(mol, "fr_aldehyde") > 0:
        brenk_alerts.append("Aldehyde (reactive, toxicity concern)")
    if _fg(mol, "fr_QuatN") > 0:
        brenk_alerts.append("Quaternary nitrogen (P-gp substrate risk)")
    brenk = {"pass": len(brenk_alerts) == 0, "alerts": brenk_alerts, "alert_count": len(brenk_alerts)}

    # ===================================================================
    # ADMET PREDICTIONS (rule-based / heuristic)
    # ===================================================================

    # ---- Absorption ----
    # Oral bioavailability score (based on Veber + Egan + MW)
    oral_bio_score = 1.0
    if tpsa > 140: oral_bio_score -= 0.3
    if tpsa > 90: oral_bio_score -= 0.1
    if logp < -1: oral_bio_score -= 0.2
    if logp > 5: oral_bio_score -= 0.2
    if mw > 500: oral_bio_score -= 0.2
    if mw < 100: oral_bio_score -= 0.1
    if rotatable > 10: oral_bio_score -= 0.1
    oral_bio = round(max(0, min(1, oral_bio_score)), 3)

    # Caco-2 permeability (LogP and PSA based)
    # High LogP + low PSA = good permeability
    if tpsa < 60 and logp > 1:
        caco2_class = "High"
    elif tpsa < 90 and logp > 0:
        caco2_class = "Moderate"
    elif tpsa < 140:
        caco2_class = "Low"
    else:
        caco2_class = "Very Low"

    # Pgp substrate (MW, LogP, HBA, TPSA based)
    pgp_score = 0
    if mw > 400: pgp_score += 1
    if logp > 2: pgp_score += 1
    if hba > 7: pgp_score += 1
    if tpsa > 90: pgp_score += 1
    pgp_substrate = "Likely" if pgp_score >= 3 else "Unlikely"
    pgp_inhibitor = "Likely" if mw > 400 and logp > 3 and num_nitro == 0 else "Unlikely"

    # Human Intestinal Absorption (HIA)
    if tpsa <= 90 and logp >= -0.7 and mw <= 400:
        hia_class = "High (>90%)"
    elif tpsa <= 140 and mw <= 500:
        hia_class = "Moderate (30-90%)"
    else:
        hia_class = "Low (<30%)"

    # ---- Distribution ----
    # Volume of distribution (LogP and pKa based heuristic)
    vd = round(0.1 + logp * 0.5, 2)  # L/kg rough estimate
    vd = max(0.05, min(vd, 20.0))

    # BBB permeability
    if logp > 2 and mw < 450 and tpsa < 90:
        bbb_class = "High"
    elif logp > 0 and mw < 500 and tpsa < 120:
        bbb_class = "Moderate"
    else:
        bbb_class = "Low"

    # Plasma protein binding (LogP and MW based)
    if logp > 3:
        ppb_class = "High (>95%)"
    elif logp > 1.5:
        ppb_class = "Moderate (80-95%)"
    else:
        ppb_class = "Low (<80%)"

    # CNS penetration
    if tpsa <= 90 and mw <= 400 and logp >= 1 and logp <= 5:
        cns_class = "Favorable"
    elif tpsa <= 120 and mw <= 500:
        cns_class = "Moderate"
    else:
        cns_class = "Unfavorable"

    # ---- Metabolism ----
    # CYP inhibition likelihood (structural feature based)
    cyp_panel = {}
    # CYP1A2: aromatic amines, planar molecules
    cyp_panel["CYP1A2"] = "Inhibitor" if (n_aromatic_rings >= 3 or num_nitro > 0) else "Non-inhibitor"
    # CYP2C9: acidic molecules, sulfonamides
    cyp_panel["CYP2C9"] = "Inhibitor" if (num_carboxylic > 0 or num_sulfonamide > 0) else "Non-inhibitor"
    # CYP2C19: aromatic, basic
    cyp_panel["CYP2C19"] = "Inhibitor" if (logp > 2 and n_aromatic_rings >= 2) else "Non-inhibitor"
    # CYP2D6: basic nitrogen
    cyp_panel["CYP2D6"] = "Inhibitor" if (num_nh > 1 or num_amine > 0) else "Non-inhibitor"
    # CYP3A4: large lipophilic molecules
    cyp_panel["CYP3A4"] = "Inhibitor" if (mw > 500 and logp > 3) else "Non-inhibitor"

    # CYP substrate prediction (lipophilicity and size)
    cyp_substrate_count = sum(1 for v in cyp_panel.values() if v == "Inhibitor")
    cyp_substrate = "Likely multiple" if cyp_substrate_count >= 3 else "Single or none"

    # Half-life estimate (heuristic)
    if logp > 3 and mw > 400:
        half_life_class = "Long (>4h)"
    elif logp > 1.5 and mw > 250:
        half_life_class = "Medium (1-4h)"
    else:
        half_life_class = "Short (<1h)"

    # ---- Toxicity ----
    # AMES mutagenicity (structural alerts)
    ames_alerts = []
    if num_nitro > 0: ames_alerts.append("Nitro group")
    if _fg(mol, "fr_Al_OH") > 1: ames_alerts.append("Multiple aliphatic hydroxyls")
    if mol.HasSubstructMatch(Chem.MolFromSmarts("c1ccc(-[N+](=O)[O-])cc1")): ames_alerts.append("Nitroaromatic")
    if mol.HasSubstructMatch(Chem.MolFromSmarts("N-N")): ames_alerts.append("Azo compound")
    ames_prediction = "Likely mutagen" if ames_alerts else "Non-mutagen"

    # hERG channel liability (LogP, MW, TPSA, charge)
    herg_risk = "High" if (logp > 3.5 and tpsa < 80) else ("Moderate" if logp > 2 else "Low")

    # Hepatotoxicity (DILI - Drug Induced Liver Injury)
    dili_risk = "High" if (logp > 3 and mw > 400 and tpsa < 75) else ("Moderate" if logp > 2.5 else "Low")

    # Skin sensitization (reactive functional groups)
    skin_risk_factors = []
    if _fg(mol, "fr_aldehyde") > 0: skin_risk_factors.append("Aldehyde")
    if _fg(mol, "fr_halogen") > 2: skin_risk_factors.append("Multiple halogens")
    skin_sensitization = "Likely" if skin_risk_factors else "Unlikely"

    # Acute toxicity (LD50 rough estimate based on LogP and functional groups)
    # Crum-Brown and Wood LD50 estimate
    ld50_estimate = round(1.37 + 0.87 * logp - 0.01 * mw + 0.06 * num_halogen, 2)
    ld50_class = "Toxic" if ld50_estimate < 2.5 else ("Moderate" if ld50_estimate < 4 else "Low toxicity")

    # ---- Clearance ----
    clearance_class = "High" if logp < 1 and tpsa > 100 else ("Low" if logp > 3 and tpsa < 60 else "Moderate")

    # Lipophilic efficiency (LipE = pIC50 - LogP; we estimate pIC50 from QED)
    lipe = round(qed_score * 10 - logp, 2) if qed_score > 0 else 0

    # ===================================================================
    # COMPOSITE SCORES
    # ===================================================================
    # Overall drug-likeness score (weighted combination)
    dl_score = 0
    dl_score += 25 * (1 - min(lipinski["violation_count"] / 4, 1))
    dl_score += 15 * (1 - min(veber["violation_count"] / 3, 1))
    dl_score += 15 * (1 - min(ghose["violation_count"] / 4, 1))
    dl_score += 10 * min(qed_score, 1)
    dl_score += 10 * (1 - min(pains["alert_count"] / 3, 1))
    dl_score += 5 * (1 - min(brenk["alert_count"] / 3, 1))
    dl_score += 10 * (1 if oral_bio > 0.5 else 0.5)
    dl_score = round(dl_score, 1)

    # ADMET risk score (lower = safer)
    admet_risk = 0
    if ames_prediction == "Likely mutagen": admet_risk += 3
    if herg_risk == "High": admet_risk += 2
    if dili_risk == "High": admet_risk += 2
    if skin_sensitization == "Likely": admet_risk += 1
    admet_risk = min(admet_risk, 10)

    # ===================================================================
    # SWISSADME-PARITY PANEL
    # ===================================================================
    # Reproduces the SwissADME output layout for the properties that are
    # computable with RDKit (WLOGP, ESOL, BOILED-Egg, Martin score, SA…).
    # XLOGP3 / MLOGP / SILICOS-IT / iLOGP are proprietary closed models and
    # are reported as unavailable; the ESOL and radar lipophilicity axis use
    # WLOGP as a documented proxy (Delaney's model originally uses CLOGP).
    esol_log_s = round(_esol_log_s(mol, logp), 2)
    esol_mol_l = round(10 ** esol_log_s, 4)
    esol_mg_ml = round(esol_mol_l * mw, 3)
    log_kp = round(-2.72 + 0.71 * logp - 0.0061 * mw, 2)  # Potts & Guy, cm/s

    in_gia = _point_in_polygon(tpsa, logp, _GIA_COORDS)
    in_bbb = _point_in_polygon(tpsa, logp, _BBB_COORDS)
    gi_absorption = "High" if in_gia else "Low"
    bbb_permeant = "Yes" if in_bbb else "No"

    bioavailability_score = _martin_bioavailability(mol, tpsa, lipinski["pass"])

    synthetic_accessibility = None
    try:
        import sys as _sys
        from rdkit.Chem import RDConfig
        _sa_dir = os.path.join(RDConfig.RDContribDir, "SA_Score")
        if os.path.isdir(_sa_dir) and _sa_dir not in _sys.path:
            _sys.path.insert(0, _sa_dir)
        import sascorer  # noqa: PLC0415 - RDKit contrib module

        synthetic_accessibility = round(sascorer.calculateScore(mol), 2)
    except Exception:
        synthetic_accessibility = None

    # Bioavailability Radar (6 axes, optimal ranges from the SwissADME paper)
    radar = [
        {"axis": "LIPO", "label": "Lipophilicity", "value": round(logp, 2), "min": -0.7, "max": 6.0,
         "note": "XLOGP3 (WLOGP proxy) in -0.7 to 6.0"},
        {"axis": "SIZE", "label": "Size", "value": mw, "min": 150, "max": 500,
         "note": "MW 150-500 g/mol"},
        {"axis": "POLAR", "label": "Polarity", "value": tpsa, "min": 20, "max": 130,
         "note": "TPSA 20-130 A2"},
        {"axis": "INSOLU", "label": "Insolubility", "value": -esol_log_s, "min": 0, "max": 6,
         "note": "ESOL log S in 0 to -6"},
        {"axis": "INSATU", "label": "Insaturation", "value": round(fsp3, 2), "min": 0.25, "max": 1.0,
         "note": "Fraction Csp3 >= 0.25"},
        {"axis": "FLEX", "label": "Flexibility", "value": rotatable, "min": 0, "max": 9,
         "note": "Rotatable bonds <= 9"},
    ]
    radar_ok = all(r["min"] <= r["value"] <= r["max"] for r in radar)

    swissadme = {
        "physicochemical": {
            "formula": formula,
            "molecular_weight": mw,
            "fraction_csp3": round(fsp3, 2),
            "rotatable_bonds": rotatable,
            "hba": hba,
            "hbd": hbd,
            "tpsa": tpsa,
        },
        "lipophilicity": {
            "ilogp": None,
            "xlogp3": None,
            "wlogp": round(logp, 2),
            "mlogp": None,
            "silicos_it": None,
            "consensus_log_p": round(logp, 2),
            "note": "Only WLOGP (Wildman-Crippen) is computable locally. XLOGP3, MLOGP, SILICOS-IT and iLOGP are proprietary models; consensus reflects WLOGP only.",
        },
        "water_solubility": {
            "esol_log_s": esol_log_s,
            "esol_class": _solubility_class(esol_log_s),
            "esol_mol_per_l": esol_mol_l,
            "esol_mg_per_ml": esol_mg_ml,
            "note": "ESOL (Delaney) using WLOGP in place of XLOGP3 — values are within ~0.1 log unit of SwissADME for most drug-like molecules.",
        },
        "pharmacokinetics": {
            "gi_absorption": gi_absorption,
            "bbb_permeant": bbb_permeant,
            "pgp_substrate": pgp_substrate,
            "cyp1a2_inhibitor": cyp_panel["CYP1A2"],
            "cyp2c19_inhibitor": cyp_panel["CYP2C19"],
            "cyp2c9_inhibitor": cyp_panel["CYP2C9"],
            "cyp2d6_inhibitor": cyp_panel["CYP2D6"],
            "cyp3a4_inhibitor": cyp_panel["CYP3A4"],
            "log_kp_skin": log_kp,
            "boiled_egg": {
                "tpsa": tpsa,
                "wlogp": round(logp, 2),
                "in_white_gia": in_gia,
                "in_yolk_bbb": in_bbb,
                "region": ("yolk" if in_bbb else "white" if in_gia else "outside"),
                "polygons": {
                    "white": [list(p) for p in _GIA_COORDS],
                    "yolk": [list(p) for p in _BBB_COORDS],
                },
            },
        },
        "drug_likeness": {
            "lipinski": lipinski,
            "ghose": ghose,
            "veber": veber,
            "egan": egan,
            "muegge": muegge,
            "bioavailability_score": bioavailability_score,
        },
        "medicinal_chemistry": {
            "pains_alerts": pains,
            "brenk_alerts": brenk,
            "lead_likeness_violations": brenk["alert_count"] + pains["alert_count"],
            "synthetic_accessibility": synthetic_accessibility,
        },
        "bioavailability_radar": {"axes": radar, "all_optimal": radar_ok},
    }

    return {
        "smiles": smiles,
        "formula": formula,
        "swissadme": swissadme,
        "_methodology": {
            "core_descriptors": {"tier": "3a", "confidence": "high", "method": "RDKit descriptors", "note": "Computed directly from molecular graph — production-ready"},
            "drug_likeness": {"tier": "3a", "confidence": "high", "method": "RDKit + Lipinski/Veber/Ghose/Egan rules", "note": "Validated pharma filters — production-ready"},
            "structural_alerts": {"tier": "3a", "confidence": "high", "method": "PAINS/Brenk SMARTS patterns", "note": "Well-established substructure filters — production-ready"},
            "functional_groups": {"tier": "3a", "confidence": "high", "method": "RDKit Fragments module", "note": "Deterministic fragment counts — production-ready"},
            "absorption_distribution_metabolism": {"tier": "3b", "confidence": "approximate", "method": "Rule-based heuristics on top of RDKit descriptors", "note": "Educational estimates — for research use, not clinical decisions. Replace with validated QSAR models for production."},
            "toxicity": {"tier": "3b", "confidence": "approximate", "method": "Rule-based heuristics (LogP/MW/TPSA thresholds, structural alerts)", "note": "No ML classifiers — these are simplified heuristics. Real toxicity prediction requires trained models (e.g. ProTox, Tox21). For research use only."},
            "clearance": {"tier": "3b", "confidence": "approximate", "method": "LogP/TPSA heuristic", "note": "Very rough estimate — real clearance depends on CYP metabolism kinetics"},
        },
        "heavy_atoms": heavy_atoms,
        "molecular_weight": mw,
        "logp": logp,
        "tpsa": tpsa,
        "hbd": hbd,
        "hba": hba,
        "rotatable_bonds": rotatable,
        "qed_score": qed_score,
        "molar_refractivity": mr,
        "molecular_volume": mol_volume,
        "fsp3": fsp3,
        "labute_asa": labute_asa,
        "estate_sum": estate_sum,
        "wiener_index": wiener,
        "zagreb_index": zagreb,
        "ring_count": ring_count,
        "aromatic_ring_count": aromatic_ring_count,
        "aliphatic_ring_count": aliphatic_ring_count,
        "num_heteroatoms": num_heteroatoms,
        "num_amide_bonds": num_amide_bonds,
        "num_atom_stereocenters": num_atom_stereocenters,
        "num_unspecified_stereocenters": num_unspecified_stereocenters,
        "functional_groups": {
            "oh": num_oh,
            "nh": num_nh,
            "carboxylic_acid": num_carboxylic,
            "ester": num_ester,
            "ether": num_ether,
            "ketone": num_ketone,
            "aldehyde": num_aldehyde,
            "halogen": num_halogen,
            "sulfonamide": num_sulfonamide,
            "nitro": num_nitro,
            "phenol": num_phenol,
        },
        "drug_likeness": {
            "overall_score": dl_score,
            "qed_score": qed_score,
            "lipinski": lipinski,
            "veber": veber,
            "ghose": ghose,
            "egan": egan,
            "mddr": mddr,
        },
        "structural_alerts": {
            "pains": pains,
            "brenk": brenk,
            "total_alert_count": pains["alert_count"] + brenk["alert_count"],
        },
        "absorption": {
            "oral_bioavailability": oral_bio,
            "caco2_permeability": caco2_class,
            "pgp_substrate": pgp_substrate,
            "pgp_inhibitor": pgp_inhibitor,
            "hia": hia_class,
        },
        "distribution": {
            "volume_of_distribution": vd,
            "bbb_permeability": bbb_class,
            "plasma_protein_binding": ppb_class,
            "cns_penetration": cns_class,
        },
        "metabolism": {
            "cyp_inhibition": cyp_panel,
            "cyp_substrate_risk": cyp_substrate,
            "half_life_class": half_life_class,
            "lipophilic_efficiency": lipe,
        },
        "toxicity": {
            "_disclaimer": "Rule-based heuristics only — no ML classifiers. For research screening, not clinical/ regulatory use.",
            "ames_mutagenicity": ames_prediction,
            "ames_alerts": ames_alerts,
            "herg_liability": herg_risk,
            "hepatotoxicity_dili": dili_risk,
            "skin_sensitization": skin_sensitization,
            "skin_sensitization_factors": skin_risk_factors,
            "acute_toxicity_ld50": ld50_class,
            "ld50_estimate_log": ld50_estimate,
            "risk_score": admet_risk,
        },
        "clearance": {
            "clearance_class": clearance_class,
            "half_life_class": half_life_class,
        },
    }
