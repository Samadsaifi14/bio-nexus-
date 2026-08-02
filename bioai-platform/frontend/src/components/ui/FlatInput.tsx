'use client';

/**
 * Neutral, flat input for data entry (PDB IDs, accession numbers,
 * FASTA sequences). Precision over decoration — visual noise here
 * increases error rate. Expressive styling is for the buttons that
 * submit these fields, not the fields themselves.
 */

export function FlatInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  const { className = '', ...rest } = props;
  return <input {...rest} className={`input-flat ${className}`} />;
}

export function FlatTextarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const { className = '', ...rest } = props;
  return <textarea {...rest} className={`input-flat resize-none font-mono ${className}`} />;
}
