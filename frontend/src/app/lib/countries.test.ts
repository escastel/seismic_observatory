import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { buildCountryCatalog } from './countries';

const feat = (properties: unknown) => ({ type: 'Feature', properties });

describe('buildCountryCatalog', () => {
  it('uses NAME_ES, then ADMIN, then the id as name', () => {
    const out = buildCountryCatalog({
      features: [
        feat({ ADM0_A3: 'AAA', NAME_ES: 'Alfa', ADMIN: 'Alpha' }),
        feat({ ADM0_A3: 'BBB', ADMIN: 'Bravo' }),
        feat({ ADM0_A3: 'CCC' }),
      ],
    });
    expect(out).toEqual([
      { id: 'AAA', name: 'Alfa' },
      { id: 'BBB', name: 'Bravo' },
      { id: 'CCC', name: 'CCC' },
    ]);
  });

  it('skips invalid ids and duplicates', () => {
    const out = buildCountryCatalog({
      features: [
        feat({ ADM0_A3: '-99', NAME_ES: 'X' }),
        feat({ ADM0_A3: '', NAME_ES: 'Y' }),
        feat({ ADM0_A3: 'TOOLONG123', NAME_ES: 'Z' }),
        feat({ ADM0_A3: 5, NAME_ES: 'W' }),
        feat({ NAME_ES: 'V' }),
        feat({ ADM0_A3: 'ESP', NAME_ES: 'España' }),
        feat({ ADM0_A3: 'ESP', NAME_ES: 'Otra' }),
      ],
    });
    expect(out).toEqual([{ id: 'ESP', name: 'España' }]);
  });

  it('sorts with Spanish collation', () => {
    const out = buildCountryCatalog({
      features: [
        feat({ ADM0_A3: 'ZZZ', NAME_ES: 'Zambia' }),
        feat({ ADM0_A3: 'AAA', NAME_ES: 'Álava' }),
        feat({ ADM0_A3: 'BBB', NAME_ES: 'Bolivia' }),
      ],
    });
    expect(out.map((c) => c.name)).toEqual(['Álava', 'Bolivia', 'Zambia']);
  });

  it('tolerates garbage input', () => {
    for (const bad of [null, undefined, 3, 'x', [], {}, { features: 1 }, { features: [null, 1, {}] }]) {
      expect(buildCountryCatalog(bad)).toEqual([]);
    }
  });

  it('builds the catalog from the real paises.geojson', () => {
    const file = resolve(process.cwd(), 'public/datos/paises.geojson');
    const out = buildCountryCatalog(JSON.parse(readFileSync(file, 'utf-8')));
    const ids = out.map((c) => c.id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(ids.length).toBeGreaterThan(150);
    expect(ids).toContain('ESP');
    expect(ids).not.toContain('-99');
    expect(ids.every((id) => id !== '')).toBe(true);
  });
});
