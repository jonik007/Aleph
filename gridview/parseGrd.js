// Surfer ASCII grid (DSAA). The first data row is the southern row.

const BLANK = 1.70141e38;

function fail(message) {
  const error = new Error(message);
  error.name = "GridError";
  return error;
}

function integer(token, name) {
  if (!/^[+-]?\d+$/.test(token)) throw fail(`${name} должно быть целым числом.`);
  const value = Number(token);
  if (!Number.isSafeInteger(value)) throw fail(`${name} слишком большое.`);
  return value;
}

function numeric(token, name) {
  const value = Number(token);
  if (!Number.isFinite(value)) throw fail(`${name} не число.`);
  return value;
}

export function parseGrd(text) {
  const tokens = String(text).replace(/^\uFEFF/, "").trim().split(/\s+/);
  if (!tokens.length || tokens[0].toUpperCase() !== "DSAA") {
    throw fail("Файл не Surfer ASCII: первая строка должна быть DSAA.");
  }
  if (tokens.length < 9) throw fail("В заголовке DSAA не хватает полей.");
  const nx = integer(tokens[1], "Число столбцов");
  const ny = integer(tokens[2], "Число строк");
  if (nx < 1 || ny < 1) throw fail("В сетке должен быть хотя бы один узел.");
  if (nx > 4000 || ny > 4000) throw fail("Сторона сетки больше 4000 узлов. Для просмотра уменьшите её.");
  const xmin = numeric(tokens[3], "xmin");
  const xmax = numeric(tokens[4], "xmax");
  const ymin = numeric(tokens[5], "ymin");
  const ymax = numeric(tokens[6], "ymax");
  const values = new Float64Array(nx * ny);
  if (tokens.length !== 9 + values.length) {
    throw fail(`В файле ${tokens.length - 9} значений, а заголовок задаёт ${nx} × ${ny}.`);
  }
  let zmin = Infinity;
  let zmax = -Infinity;
  let blanks = 0;
  for (let i = 0; i < values.length; i++) {
    const z = numeric(tokens[9 + i], `значение ${i + 1}`);
    if (z >= BLANK * 0.999) {
      values[i] = NaN;
      blanks += 1;
    } else {
      values[i] = z;
      if (z < zmin) zmin = z;
      if (z > zmax) zmax = z;
    }
  }
  if (blanks === values.length) throw fail("В сетке нет ни одного числового значения.");
  return { nx, ny, xmin, xmax, ymin, ymax, zmin, zmax, blanks, values };
}

export function sameShape(a, b) {
  return a.nx === b.nx && a.ny === b.ny;
}
