import sharp from 'sharp';
import {fileURLToPath} from 'node:url';
process.chdir(fileURLToPath(new URL('.',import.meta.url)));
import { mkdir, readFile } from 'node:fs/promises';
await mkdir('public/icons', {recursive:true});
const brands = JSON.parse(await readFile('theme/brands.json','utf8'));
for (const [theme,{color}] of Object.entries(brands)) {
 const source = `public/brand/${theme}-square.svg`;
 for (const size of [180,192,512]) await sharp(source).resize(size,size).png().toFile(`public/icons/${theme}-${size}.png`);
 const inset = await sharp(await readFile(source)).resize(360,360).png().toBuffer();
 await sharp({create:{width:512,height:512,channels:4,background:color}}).composite([{input:inset,left:76,top:76}]).png().toFile(`public/icons/${theme}-maskable.png`);
}
