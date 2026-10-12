declare module 'igv' {
  interface BrowserOptions {
    genome?: string;
    reference?: { fastaURL: string; indexURL?: string };
    tracks?: TrackOptions[];
    locus?: string;
    showNavigation?: boolean;
    showRuler?: boolean;
  }

  interface TrackOptions {
    name: string;
    url: string;
    indexURL?: string;
    format?: string;
    type?: string;
    color?: string;
    height?: number;
    indexed?: boolean;
    displayMode?: string;
  }

  interface Browser {
    loadTrack(config: TrackOptions): Promise<void>;
    goto(locus: string): void;
    setReference(config: { fastaURL: string }): void;
    removeTrackByName(name: string): void;
    destroy(): void;
  }

  function createBrowser(container: HTMLElement, options: BrowserOptions): Promise<Browser>;
}
