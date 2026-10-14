/**
 * Disabled scientific prototype, retained for code-history reference.
 * APK/code inventory is not molecular evidence. Its scientific entry point
 * fails closed; this module must not be imported into browser analysis pages.
 */
/**
 * Docking Validation Feature using REA Reverse Engineering
 * 
 * This module implements docking validation, interaction fingerprints,
 * and auto-box from pockets using REA's Android APK inspection capabilities.
 * 
 * REA CLI Integration:
 * - Command: `rea inspect-android-package <apk-path>`
 * - Output format: JSON Evidence bundle
 * - Path is a positional argument, not a flag
 * 
 * Feature Priority: HIGHEST (Priority 1 from feature list)
 */

import { execFileSync } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';

/**
 * REA Command execution helper
 * Runs `rea <command> <positional_args> ...` and returns parsed JSON result
 */
function runReaCommand(command: string, args: string[]): Promise<any> {
  try {
    const output = execFileSync('rea', [command, ...args], { 
      encoding: 'utf8',
      timeout: 120000,
      maxBuffer: 10 * 1024 * 1024
    });
    return JSON.parse(output.trim());
  } catch (error: any) {
    return { 
      code: 'EXECUTION_ERROR', 
      message: error.message || 'Unknown execution error',
      stdout: error.stdout,
      stderr: error.stderr 
    };
  }
}

/**
 * Docking pocket detection results from APK analysis
 */
export interface PocketDetection {
  pocketId: string;
  residueRange: [number, number];
  hydrophobicity: 'hydrophobic' | 'polar' | 'charged';
  volume: 'small' | 'medium' | 'large';
  potentialLigands: string[];
  is_pocket: boolean;
  residue_count: number;
  confidence: number;
}

/**
 * Interaction fingerprint between ligand and protein
 */
export interface InteractionFingerprint {
  hydrogenBondDonors: number;
  hydrogenBondAcceptors: number;
  hydrophobicContacts: number;
  piStacking: boolean;
  saltBridges: number;
  vanDerWaalsContacts: number;
  rootMeanSquareDeviation: number;
  total_interactions: number;
  hbond_count: number;
}

/**
 * Auto-box parameters from pocket detection
 */
export interface AutoBoxParameters {
  centerX: number;
  centerY: number;
  centerZ: number;
  sizeX: number;
  sizeY: number;
  sizeZ: number;
  padding: number;
}

/**
 * Docking validation result
 */
export interface DockingValidationResult {
  success: boolean;
  pocketDetections: PocketDetection[];
  interactionFingerprint: InteractionFingerprint;
  autoBox: AutoBoxParameters;
  confidenceScore: number; // 0-100
  evidenceIds: string[];
  limitations: string[];
  rawReeaOutput: any; // Full REA output for audit
}

/**
 * Run docking validation using REA on an Android APK
 * 
 * @param apkPath Absolute path to the APK file to analyze
 * @returns Docking validation result with pocket detection and auto-box parameters
 */
export async function runDockingValidation(apkPath: string): Promise<DockingValidationResult> {
  void apkPath;
  throw new Error(
    'APK inspection cannot validate molecular docking, detect structural pockets, compute interactions or define a docking box. Use the structure-based docking workflow with recorded molecular coordinates.'
  );
}

/**
 * Create fallback result when REA commands are unavailable
 */
function createFallbackResult(apkPath: string, reason: string): DockingValidationResult {
  return {
    success: false,
    pocketDetections: [],
    interactionFingerprint: {
      hydrogenBondDonors: 0,
      hydrogenBondAcceptors: 0,
      hydrophobicContacts: 0,
      piStacking: false,
      saltBridges: 0,
      vanDerWaalsContacts: 0,
      rootMeanSquareDeviation: 0.0,
      total_interactions: 0,
      hbond_count: 0
    },
    autoBox: {
      centerX: 0,
      centerY: 0,
      centerZ: 0,
      sizeX: 10,
      sizeY: 10,
      sizeZ: 10,
      padding: 5
    },
    confidenceScore: 0,
    evidenceIds: [],
    limitations: [
      'REA inspection unavailable: ' + reason,
      'Pocket detection relies on 3D structural data, not code analysis',
      'Interaction fingerprints require empirical MD data',
      'Auto-box parameters need actual binding site coordinates'
    ],
    rawReeaOutput: { reason }
  };
}

/**
 * Extract pocket detection information from REA analysis results
 */
function extractPocketDetections(
  inspectResult: any,
  classSearch: any,
  dockingMethods: any[],
  traceResults: any[]
): PocketDetection[] {
  const pockets: PocketDetection[] = [];

  // Analyze method bodies for pocket-like patterns
  for (const method of dockingMethods) {
    const body = method.pseudocode || method.body || method.rawResult?.text || '';
    
    if (!body) continue;
    
    // Look for three-letter amino acid codes (protein residue patterns)
    const aaPattern = /[A-Z][a-z]{2}/g;
    const aaMatches = body.match(aaPattern);
    
    if (aaMatches && aaMatches.length >= 3) {
      // Found amino acid sequences - potential pocket residues
      const uniqueAAs = [...new Set(aaMatches)].map(aa => aa.toUpperCase());
      
      pockets.push({
        pocketId: 'pocket-' + uniqueAAs.join('-'),
        residueRange: [0, 0], // Will be refined with actual structural data
        hydrophobicity: classifyHydrophobicity(uniqueAAs),
        volume: classifyVolume(uniqueAAs),
        potentialLigands: extractPotentialLigands(body),
        is_pocket: true,
        residue_count: uniqueAAs.length,
        confidence: Math.min(uniqueAAs.length * 10, 100),
      });
    }
  }

  // Augment with trace results - look for pocket-related variables
  for (const trace of traceResults) {
    const traceSymbol = trace.symbol || trace.variable || trace.name;
    if (traceSymbol && !pockets.some(p => p.pocketId === traceSymbol)) {
      pockets.push({
        pocketId: traceSymbol.startsWith('pocket-') ? traceSymbol : 'pocket-' + traceSymbol,
        residueRange: [0, 0],
        hydrophobicity: 'polar',
        volume: 'medium',
        potentialLigands: [traceSymbol],
        is_pocket: false,
        residue_count: 0,
        confidence: 0,
      });
    }
  }

  // If no pockets found from methods/traces, try searching class names
  if (pockets.length === 0 && classSearch && classSearch.classes) {
    for (const className of classSearch.classes.slice(0, 5)) {
      pockets.push({
        pocketId: 'pocket-' + className.replace(/\./g, '-'),
        residueRange: [0, 0],
        hydrophobicity: 'polar',
        volume: 'medium',
        potentialLigands: [className],
        is_pocket: false,
        residue_count: 0,
        confidence: 0,
      });
    }
  }

  return pockets;
}

/**
 * Classify hydrophobicity based on amino acid codes
 */
function classifyHydrophobicity(aas: string[]): 'hydrophobic' | 'polar' | 'charged' {
  const hydrophobic = ['ALA', 'VAL', 'LEU', 'ILE', 'MET', 'PHE', 'TRP', 'PRO'];
  const polar = ['SER', 'THR', 'CYS', 'TYR', 'ASN', 'GLN'];
  const charged = ['ASP', 'GLU', 'LYS', 'ARG', 'HIS'];

  const aaSet = new Set(aas.map(aa => aa.toUpperCase()));

  const hasCharged = charged.some(aa => aaSet.has(aa));
  const hasHydrophobic = hydrophobic.some(aa => aaSet.has(aa));
  const hasPolar = polar.some(aa => aaSet.has(aa));

  if (hasCharged) return 'charged';
  if (hasHydrophobic) return 'hydrophobic';
  if (hasPolar) return 'polar';
  return 'polar';
}

/**
 * Classify volume based on amino acid codes
 */
function classifyVolume(aas: string[]): 'small' | 'medium' | 'large' {
  const small = ['GLY', 'ALA'];
  const medium = ['VAL', 'SER', 'CYS', 'THR'];
  const large = ['LEU', 'ILE', 'MET', 'PHE', 'TYR', 'TRP', 'PRO', 'ASP', 'GLU', 'LYS', 'ARG'];

  const aaSet = new Set(aas.map(aa => aa.toUpperCase()));

  if (large.some(aa => aaSet.has(aa))) return 'large';
  if (medium.some(aa => aaSet.has(aa))) return 'medium';
  return 'small';
}

/**
 * Extract potential ligand candidates from method body
 */
function extractPotentialLigands(body: string): string[] {
  const ligands: string[] = [];
  
  if (!body) return ligands;

  // Look for common ligand-related terms
  const ligandPatterns = [
    /ligand/gi,
    /cofactor/gi,
    /inhibitor|agonist|antagonist/gi
  ];

  for (const pattern of ligandPatterns) {
    const matches = body.match(pattern);
    if (matches) {
      matches.forEach(function(m) {
        var normalized = m.toLowerCase();
        if (!ligands.includes(normalized)) ligands.push(normalized);
      });
    }
  }

  // Also look for small molecule names (common bioinformatics patterns)
  var smallMoleculePatterns = body.match(/\b(ATP|GTP|GDP|cAMP|cGMP|NAD|NADH|FAD|FMN|SAM|S-adenosyl)\b/gi);
  if (smallMoleculePatterns) {
    smallMoleculePatterns.forEach(function(s) {
      if (!ligands.includes(s.toLowerCase())) ligands.push(s.toLowerCase());
    });
  }

  // Look for common drug-like patterns
  var drugPatterns = body.match(/\b([A-Z][a-z]+)\b/g);
  if (drugPatterns) {
    var drugBlacklist = ['API', 'CPU', 'RAM', 'ROM', 'HTML', 'CSS', 'JS', 'XML', 'JSON'];
    for (var i = 0; i < drugPatterns.length; i++) {
      var s = drugPatterns[i];
      if (!drugBlacklist.includes(s) && !ligands.includes(s.toLowerCase()) && s.length >= 3) {
        ligands.push(s);
      }
    }
  }

  return ligands.slice(0, 10).map(function(l) { return l.toLowerCase(); });
}

/**
 * Compute interaction fingerprint from pocket detections and traces
 */
function computeInteractionFingerprint(
  pocketDetections: PocketDetection[],
  traceResults: any[]
): InteractionFingerprint {
  var hbondDonors = 0;
  var hbondAcceptors = 0;
  var hydrophobicContacts = 0;
  var piStacking = false;
  var saltBridges = 0;
  var vdwContacts = 0;

  // Analyze trace results for interaction patterns
  for (var i = 0; i < traceResults.length; i++) {
    var trace = traceResults[i];
    var callText = (trace as any).rawResult?.text || 
                     (trace as any).body || 
                     (trace as any).pseudocode || '';
    
    if (!callText) continue;
    
    var textLower = callText.toLowerCase();
    
    if (/hydrogen.?bond|h-bond/i.test(textLower)) {
      if (/donor/i.test(textLower)) hbondDonors++;
      if (/acceptor/i.test(textLower)) hbondAcceptors++;
    }
    if (/hydrophobic|hydrophobe/i.test(textLower)) hydrophobicContacts++;
    if (/pi.stack|aromatic|ring/i.test(textLower)) piStacking = true;
    if (/salt.?bridge|ion.pair|charge.charge/i.test(textLower)) saltBridges++;
    if (/van.?der.?waals|vdw|lennard/i.test(textLower)) vdwContacts++;
  }

  // Also analyze pocket detection results for heuristics
  for (var j = 0; j < pocketDetections.length; j++) {
    var pocket = pocketDetections[j];
    if (pocket.hydrophobicity === 'hydrophobic') {
      hydrophobicContacts += 2;
    }
    if (pocket.hydrophobicity === 'polar') {
      hbondDonors += 1;
      hbondAcceptors += 1;
    }
    if (pocket.hydrophobicity === 'charged') {
      saltBridges += 1;
      vdwContacts += 1;
    }
  }

  return {
    hydrogenBondDonors: Math.max(hbondDonors, 0),
    hydrogenBondAcceptors: Math.max(hbondAcceptors, 0),
    hydrophobicContacts: Math.max(hydrophobicContacts, 0),
    piStacking,
    saltBridges: Math.max(saltBridges, 0),
    vanDerWaalsContacts: Math.max(vdwContacts, 0),
    rootMeanSquareDeviation: 0.0, // Would be computed from actual docking
    total_interactions: Math.max(hbondDonors + hydrophobicContacts + (saltBridges > 0 ? 1 : 0) + (piStacking ? 1 : 0), 0),
    hbond_count: Math.max(hbondDonors + hbondAcceptors, 0)
  };
}

/**
 * Compute auto-box parameters from pocket detections
 */
function computeAutoBoxParameters(pocketDetections: PocketDetection[]): AutoBoxParameters {
  if (pocketDetections.length === 0) {
    return {
      centerX: 0,
      centerY: 0,
      centerZ: 0,
      sizeX: 10,
      sizeY: 10,
      sizeZ: 10,
      padding: 5,
    };
  }

  // Compute centroid based on residue ranges
  var sumStart = 0, sumEnd = 0;
  var minStart = Infinity, maxStart = -Infinity;
  var minEnd = Infinity, maxEnd = -Infinity;

  for (var k = 0; k < pocketDetections.length; k++) {
    var pocket = pocketDetections[k];
    var rangeStart = pocket.residueRange[0];
    var rangeEnd = pocket.residueRange[1];
    sumStart += rangeStart;
    sumEnd += rangeEnd;
    
    if (rangeStart < minStart) minStart = rangeStart;
    if (rangeEnd > maxStart) maxStart = rangeEnd;
    if (rangeStart < minEnd) minEnd = rangeStart;
    if (rangeEnd > maxEnd) maxEnd = rangeEnd;
  }

  var centerX = (minStart + maxStart) / 2;
  var centerY = (minEnd + maxEnd) / 2;
  // Z is approximated as Y for simplicity without 3D data
  var centerZ = centerY;
  
  var sizeX = Math.max(maxStart - minStart + 2 * 5, 10);
  var sizeY = Math.max(maxEnd - minEnd + 2 * 5, 10);
  var sizeZ = sizeY; // Symmetric assumption

  return {
    centerX: centerX,
    centerY: centerY,
    centerZ: centerZ,
    sizeX: sizeX,
    sizeY: sizeY,
    sizeZ: sizeZ,
    padding: 5,
  };
}

/**
 * Compute confidence score for docking validation
 */
function computeConfidenceScore(
  pocketDetections: PocketDetection[],
  interactionFingerprint: InteractionFingerprint,
  autoBox: AutoBoxParameters
): number {
  var score = 0;
  
  // Base score from pocket detection quantity and quality
  score += Math.min(pocketDetections.length * 10, 40);
  
  // Score from interaction fingerprint completeness
  score += Math.min(interactionFingerprint.hydrogenBondDonors * 3, 15);
  score += Math.min(interactionFingerprint.hydrogenBondAcceptors * 3, 15);
  score += Math.min(interactionFingerprint.hydrophobicContacts * 2, 10);
  if (interactionFingerprint.piStacking) { score += 5; }
  score += Math.min(interactionFingerprint.saltBridges * 2, 8);
  score += Math.min(interactionFingerprint.vanDerWaalsContacts * 1, 5);
  
  // Score from auto-box quality
  if (autoBox.sizeX > 0 && autoBox.sizeY > 0 && autoBox.sizeZ > 0) {
    score += 10;
  }
  if (autoBox.padding > 0) {
    score += 3;
  }
  
  // Cap at 100
  return Math.min(Math.round(score), 100);
}

/**
 * Identify limitations of the docking validation
 */
function identifyLimitations(
  inspectResult: any,
  classSearch: any,
  dockingMethods: any[],
  traceResults: any[]
): string[] {
  var limitations: string[] = [];

  // REA-specific limitations
  if (inspectResult.code && inspectResult.code !== 'success') {
    limitations.push('APK inspection failed: ' + (inspectResult.message || inspectResult.code));
  } else if (!inspectResult.success) {
    limitations.push('APK inspection did not report success');
  }

  if (!classSearch || !classSearch.classes || classSearch.classes.length === 0) {
    limitations.push('No docking-related classes found in APK');
  }

  if (dockingMethods.length === 0) {
    limitations.push('No docking-related methods decompiled from APK');
  }

  if (traceResults.length === 0) {
    limitations.push('No references traced to docking pockets');
  }

  // General bioinformatics limitations
  limitations.push(
    'Pocket detection relies on sequence pattern matching from decompiled code, not 3D structural data',
    'Interaction fingerprints based on code pattern analysis, not empirical molecular dynamics',
    'Auto-box parameters derived from residue ranges, not actual binding site coordinates or volumes',
    'Confidence score is heuristic, not based on validated docking scores (e.g., Vina, Glide, AutoDock)',
    'Amino acid classification is based on generic property tables, not protein-specific contexts',
    'Ligand candidate extraction is pattern-based, not structure-based screening'
  );

  return limitations;
}

/**
 * Extract evidence IDs from REA inspection result
 */
function extractEvidenceIds(result: any): string[] {
  var ids: string[] = [];
  
  // Try various evidence ID fields
  var possibleFields = ['evidence_id', 'EvidenceId', 'evidenceId', 'id', 'EvidenceID'];
  
  for (var field = 0; field < possibleFields.length; field++) {
    var fieldName = possibleFields[field];
    if (result[fieldName]) {
      if (typeof result[fieldName] === 'string' && result[fieldName].startsWith('ev_')) {
        ids.push(result[fieldName]);
      } else if (Array.isArray(result[fieldName])) {
        result[fieldName].forEach(function(id) {
          if (typeof id === 'string' && id.startsWith('ev_')) {
            ids.push(id);
          }
        });
      }
    }
  }
  
  // Deduplicate
  return ids.filter(function(value, index, self) { 
    return self.indexOf(value) === index; 
  });
}

/**
 * Example usage with a real APK path
 * 
 * const result = await runDockingValidation('/path/to/docking-target.apk');
 * console.log('Docking Validation Result:', JSON.stringify(result, null, 2));
 */