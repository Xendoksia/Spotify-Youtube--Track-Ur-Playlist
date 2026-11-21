/** A summary slide as a story picture (1080 x 1920) to share, as the phone's storyImage (wrapped_stage.dart): the
 * stage in the slide's hue with its lights held still, the slide as a card in the middle, and the summary's name
 * with the app's under it. A slide with a picture behind it (fill: the first one's wall of covers) covers the whole
 * picture instead, darker under the names so they stay readable. */

const WIDTH = 1080;
const HEIGHT = 1920;

function load(source: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = reject;
    image.src = source;
  });
}

export async function storyImage(slide: string, hue: number, title: string, fill = false): Promise<string> {
  const picture = await load(slide);
  const canvas = document.createElement("canvas");
  canvas.width = WIDTH;
  canvas.height = HEIGHT;
  const context = canvas.getContext("2d")!;

  const stage = context.createLinearGradient(0, 0, WIDTH, HEIGHT);
  stage.addColorStop(0, `oklch(0.42 0.13 ${hue})`);
  stage.addColorStop(1, `oklch(0.2 0.07 ${hue + 30})`);
  context.fillStyle = stage;
  context.fillRect(0, 0, WIDTH, HEIGHT);
  const lights: [number, number, string][] = [
    [0.2, 0.15, `oklch(0.64 0.17 ${hue + 50} / 0.55)`],
    [0.85, 0.8, `oklch(0.56 0.16 ${hue - 60} / 0.45)`],
    [0.55, 0.45, `oklch(0.72 0.12 ${hue + 150} / 0.22)`],
  ];
  for (const [x, y, color] of lights) {
    const radius = HEIGHT * 0.5;
    const light = context.createRadialGradient(WIDTH * x, HEIGHT * y, 0, WIDTH * x, HEIGHT * y, radius);
    light.addColorStop(0, color);
    light.addColorStop(1, "transparent");
    context.fillStyle = light;
    context.fillRect(0, 0, WIDTH, HEIGHT);
  }

  if (fill) {
    // Over all of it, cut at the edges, with a shade under the names
    const scale = Math.max(WIDTH / picture.width, HEIGHT / picture.height);
    const width = picture.width * scale;
    const height = picture.height * scale;
    context.imageSmoothingQuality = "high";
    context.drawImage(picture, (WIDTH - width) / 2, (HEIGHT - height) / 2, width, height);
    const shade = context.createLinearGradient(0, HEIGHT - 420, 0, HEIGHT);
    shade.addColorStop(0, "transparent");
    shade.addColorStop(1, `oklch(0.2 0.07 ${hue + 30} / 0.95)`);
    context.fillStyle = shade;
    context.fillRect(0, HEIGHT - 420, WIDTH, 420);
    footer(context, title);
    return canvas.toDataURL("image/png");
  }

  // The slide as a rounded card, as big as it fits between a margin and the footer
  const area = { x: 48, y: 120, width: WIDTH - 96, height: HEIGHT - 120 - 260 };
  const scale = Math.min(area.width / picture.width, area.height / picture.height);
  const width = picture.width * scale;
  const height = picture.height * scale;
  const x = area.x + (area.width - width) / 2;
  const y = area.y + (area.height - height) / 2;
  context.save();
  context.shadowColor = "rgb(0 0 0 / 0.35)";
  context.shadowBlur = 40;
  context.shadowOffsetY = 12;
  context.beginPath();
  context.roundRect(x, y, width, height, 36);
  context.fillStyle = "rgb(0 0 0 / 0.2)";
  context.fill();
  context.restore();
  context.save();
  context.beginPath();
  context.roundRect(x, y, width, height, 36);
  context.clip();
  context.imageSmoothingQuality = "high";
  context.drawImage(picture, x, y, width, height);
  context.restore();
  context.beginPath();
  context.roundRect(x, y, width, height, 36);
  context.strokeStyle = "rgb(255 255 255 / 0.22)";
  context.lineWidth = 2;
  context.stroke();

  footer(context, title);
  return canvas.toDataURL("image/png");
}

/** The summary's name with the app's under it, at the bottom */
function footer(context: CanvasRenderingContext2D, title: string) {
  context.textAlign = "center";
  context.textBaseline = "alphabetic";
  context.fillStyle = "rgb(255 255 255 / 0.75)";
  context.font = "600 32px 'Segoe UI Variable Text', 'Segoe UI', sans-serif";
  context.fillText(title, WIDTH / 2, HEIGHT - 160, WIDTH - 96);
  context.fillStyle = "#fff";
  context.font = "800 40px 'Segoe UI Variable Display', 'Segoe UI', sans-serif";
  context.fillText("Playlist Tracker", WIDTH / 2, HEIGHT - 110);
}
