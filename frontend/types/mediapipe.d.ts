declare module "@mediapipe/tasks-vision" {
  export type FilesetResolver = any;
  export type HandLandmarker = any;
  export type FaceLandmarker = any;
  export type HandLandmarkerResult = any;
  export type FaceLandmarkerResult = any;
  export const FilesetResolver: {
    forVisionTasks(basePath: string): Promise<FilesetResolver>;
  };
  export const HandLandmarker: {
    createFromOptions(fileset: FilesetResolver, options: Record<string, unknown>): Promise<HandLandmarker>;
  };
  export const FaceLandmarker: {
    createFromOptions(fileset: FilesetResolver, options: Record<string, unknown>): Promise<FaceLandmarker>;
  };
}
