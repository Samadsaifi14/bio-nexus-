"""RO-Crate 1.1 metadata/evidence ZIP for an owned recorded workflow.

This is not a Workflow Run RO-Crate profile conformance claim. Unavailable inputs
and outputs are never fabricated as payload files or completed actions.
"""
from __future__ import annotations
import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone
from app.services.workflow_manifest import build_workflow_manifest


def build_workflow_rocrate(experiment: dict, provenance: list[dict]) -> bytes:
    manifest = build_workflow_manifest(experiment, provenance)
    evidence = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2).encode('utf-8')
    descriptor = {'@id': 'ro-crate-metadata.json', '@type': 'CreativeWork',
                  'conformsTo': {'@id': 'https://w3id.org/ro/crate/1.1'}, 'about': {'@id': './'}}
    root = {'@id': './', '@type': 'Dataset',
            'name': f"BioNexus recorded workflow {experiment.get('experiment_id') or experiment.get('job_id') or 'unidentified'}",
            'description': 'Metadata and recorded evidence only. This package does not contain raw scientific inputs/results and does not reproduce or execute a workflow.',
            'datePublished': datetime.now(timezone.utc).isoformat(),
            'license': 'No reuse license recorded for the underlying research data.',
            'hasPart': [{'@id': 'workflow-evidence.json'}], 'mentions': []}
    graph = [descriptor, root,
             {'@id': 'workflow-evidence.json', '@type': 'File', 'name': 'Recorded workflow evidence',
              'encodingFormat': 'application/json', 'contentSize': len(evidence),
              'identifier': 'urn:sha256:' + hashlib.sha256(evidence).hexdigest()}]
    for index, node in enumerate(manifest['steps']):
        node_id = f'#step-{index}'
        software_id = f'#software-{index}'
        software = {'@id': software_id, '@type': 'SoftwareApplication', 'name': node.get('tool') or 'Unrecorded tool'}
        if node.get('tool_version'):
            software['softwareVersion'] = str(node['tool_version'])
        graph.append(software)
        action_status = {'COMPLETED': 'CompletedActionStatus', 'FAILED': 'FailedActionStatus',
                         'RUNNING': 'ActiveActionStatus'}.get(node['state'])
        step = {'@id': node_id, '@type': 'CreateAction' if action_status else 'CreativeWork',
                'name': str(node['id']), 'description': f"Recorded state: {node['state']}; detailed evidence and missing provenance are in workflow-evidence.json"}
        if action_status:
            step['actionStatus'] = {'@id': 'http://schema.org/' + action_status}
            step['instrument'] = {'@id': software_id}
        if node.get('completed_at') and node['state'] in {'COMPLETED', 'FAILED'}:
            step['endTime'] = node['completed_at']
        graph.append(step)
        root['mentions'].extend([{'@id': node_id}, {'@id': software_id}])
    metadata = {'@context': 'https://w3id.org/ro/crate/1.1/context', '@graph': graph}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('ro-crate-metadata.json', json.dumps(metadata, ensure_ascii=False, indent=2))
        archive.writestr('workflow-evidence.json', evidence)
        archive.writestr('README.txt', 'BioNexus metadata/evidence RO-Crate.\nContains no raw inputs or scientific output files.\nMissing provenance is explicit in workflow-evidence.json.\nRO-Crate specification: https://w3id.org/ro/crate/1.1\n')
    return buffer.getvalue()
