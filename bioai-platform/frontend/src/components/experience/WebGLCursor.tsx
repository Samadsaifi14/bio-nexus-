'use client';

import { useEffect, useRef } from 'react';

/** A short, demand-rendered WebGL ripple. Retains the OS pointer and never intercepts input. */
export function WebGLCursor() {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const element = canvas.current;
    if (!element) return;
    const media = window.matchMedia('(pointer: fine) and (min-width: 1024px) and (prefers-reduced-motion: no-preference)');
    let cleanup: (() => void) | undefined;
    const setup = () => {
      cleanup?.(); cleanup = undefined;
      if (!media.matches) return;
      const gl = element.getContext('webgl', { alpha: true, premultipliedAlpha: false, powerPreference: 'low-power' });
      if (!gl) return;
      const shader = (type: number, source: string) => {
        const result = gl.createShader(type)!; gl.shaderSource(result, source); gl.compileShader(result); return result;
      };
      const vertex = shader(gl.VERTEX_SHADER, 'attribute vec2 position; void main(){gl_Position=vec4(position,0.,1.);}');
      const fragment = shader(gl.FRAGMENT_SHADER, 'precision mediump float; uniform vec2 resolution; uniform vec2 pointer; uniform float fade; void main(){vec2 p=gl_FragCoord.xy-pointer; float d=length(p); float ring=1.-smoothstep(1.,2.5,abs(d-18.)); gl_FragColor=vec4(.17,.44,.40,ring*fade*.4);}');
      const program = gl.createProgram()!; gl.attachShader(program, vertex); gl.attachShader(program, fragment); gl.linkProgram(program);
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) { gl.deleteProgram(program); gl.deleteShader(vertex); gl.deleteShader(fragment); return; }
      gl.useProgram(program);
      const buffer = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buffer); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]), gl.STATIC_DRAW);
      const position = gl.getAttribLocation(program, 'position'); gl.enableVertexAttribArray(position); gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
      const pointer = gl.getUniformLocation(program, 'pointer'), fade = gl.getUniformLocation(program, 'fade');
      let raf = 0, last = 0;
      const resize = () => { element.width = innerWidth; element.height = innerHeight; gl.viewport(0, 0, element.width, element.height); };
      const clear = () => { cancelAnimationFrame(raf); raf = 0; gl.clearColor(0,0,0,0); gl.clear(gl.COLOR_BUFFER_BIT); };
      const draw = (now: number) => {
        const alpha = Math.max(0, 1 - (now - last) / 450);
        gl.uniform1f(fade, alpha); gl.drawArrays(gl.TRIANGLES, 0, 6);
        raf = alpha > 0 ? requestAnimationFrame(draw) : 0;
      };
      const move = (event: PointerEvent) => {
        if (!(event.target instanceof Element) || event.target.closest('input, textarea, select, [contenteditable], [data-scientific-surface], .bn-immersive[data-motion="paused"]') || document.hidden) { clear(); return; }
        gl.uniform2f(pointer, event.clientX, innerHeight - event.clientY); last = performance.now();
        if (!raf) raf = requestAnimationFrame(draw);
      };
      resize(); window.addEventListener('resize', resize); window.addEventListener('pointermove', move, { passive: true });
      document.addEventListener('pointerleave', clear); document.addEventListener('visibilitychange', clear);
      cleanup = () => { clear(); window.removeEventListener('resize', resize); window.removeEventListener('pointermove', move); document.removeEventListener('pointerleave', clear); document.removeEventListener('visibilitychange', clear); gl.deleteBuffer(buffer); gl.deleteProgram(program); gl.deleteShader(vertex); gl.deleteShader(fragment); };
    };
    setup(); media.addEventListener('change', setup);
    return () => { media.removeEventListener('change', setup); cleanup?.(); };
  }, []);
  return <canvas ref={canvas} className="bn-webgl-cursor" aria-hidden="true" />;
}
