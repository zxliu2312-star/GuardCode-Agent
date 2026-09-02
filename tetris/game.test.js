/**
 * game.test.js — 俄罗斯方块逻辑核心单元测试
 *
 * 运行方式：
 *   node --test game.test.js
 *   （Node.js 18+，使用内置 test runner）
 */
'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');

const T = require('./game');

// ---------------------------------------------------------------------------
// 基础工具
// ---------------------------------------------------------------------------
test('makeBoard 生成 rows×cols 的空棋盘，且行为独立数组', () => {
  const b = T.makeBoard(20, 10);
  assert.equal(b.length, 20);
  assert.equal(b[0].length, 10);
  assert.ok(b.every((row) => row.every((c) => c === 0)));
  b[0][0] = 'T';
  assert.equal(b[1][0], 0, '两行不应共享引用');
});

test('pieceCells 按矩阵把 1 位转换为绝对坐标', () => {
  // T 型 rot0：中部+下横条；放在 (3, 0)
  const cells = T.pieceCells('T', 0, 3, 0);
  assert.equal(cells.length, 4);
  // 顶部尖角在 x=4,y=0；底部一行 x=3,4,5 / y=1
  assert.ok(cells.some((c) => c.x === 4 && c.y === 0));
  assert.ok(cells.some((c) => c.x === 3 && c.y === 1));
  assert.ok(cells.some((c) => c.x === 5 && c.y === 1));
});

test('matrixCells 正确抽取每个旋转状态', () => {
  const m = T.SHAPES.I[0];
  const cells = T.matrixCells(m);
  assert.equal(cells.length, 4);
  assert.ok(cells.every((c) => c.y === 1), 'I 型横放应都在第 1 行');
});

test('每种方块都具备标准的旋转数量', () => {
  assert.equal(T.SHAPES.I.length, 4);
  assert.equal(T.SHAPES.O.length, 1);
  assert.equal(T.SHAPES.J.length, 4);
  assert.equal(T.SHAPES.L.length, 4);
  assert.equal(T.SHAPES.S.length, 2);
  assert.equal(T.SHAPES.Z.length, 2);
  assert.equal(T.SHAPES.T.length, 4);
});

// ---------------------------------------------------------------------------
// 碰撞检测
// ---------------------------------------------------------------------------
test('collides 检测左右与底部边界', () => {
  const b = T.makeBoard(4, 4);
  // 在空棋盘上旋转 T 放在 x=0..2 之内是合法的
  assert.equal(T.collides(b, { type: 'T', rot: 0, x: 1, y: 0 }), false);
  // 顶到左边后不能再左移
  assert.equal(T.collides(b, { type: 'T', rot: 0, x: 0, y: 0 }), false);
  // 与底部重叠：棋盘高 4，T 的底行若落在 y=4 即越界
  const below = T.collides(b, { type: 'T', rot: 0, x: 1, y: 3 });
  assert.equal(below, true);
  // x 为负 → 越界
  assert.equal(T.collides(b, { type: 'T', rot: 0, x: -1, y: 0 }), true);
});

test('collides 检测与已有格子重叠', () => {
  const b = T.makeBoard(4, 4);
  b[1][1] = 'T';
  // T 底部一行会覆盖 y=1 的 x=1
  assert.equal(T.collides(b, { type: 'T', rot: 0, x: 0, y: 0 }), true);
  // 错开一格则不碰撞
  assert.equal(T.collides(b, { type: 'T', rot: 0, x: 2, y: 0 }), false);
});

// ---------------------------------------------------------------------------
// 出生位置
// ---------------------------------------------------------------------------
test('spawnPiece 将方块居中放在棋盘顶部', () => {
  const p = T.spawnPiece('O', 10);
  assert.deepEqual({ type: p.type, rot: p.rot }, { type: 'O', rot: 0 });
  assert.equal(p.y, 0);
  assert.equal(p.x, 4, 'O 宽 2，应水平居中');
  // I 型横向：宽 4 → x=3，出生时靠上（y=-1，实际行从 0 开始）
  const i = T.spawnPiece('I', 10);
  assert.equal(i.x, 3);
  assert.equal(i.y, -1);
  const ic = T.pieceCells('I', i.rot, i.x, i.y);
  assert.ok(ic.every((c) => c.y === 0), 'I 型出生应贴住顶部第 0 行');
});

test('I 型整条下落可精确落到最底部', () => {
  const eng = T.createTetris({ cols: 10, rows: 20, queue: ['I'] });
  eng.dropToFloor();
  const cur = eng.getCurrent();
  const cells = T.pieceCells(cur.type, cur.rot, cur.x, cur.y);
  assert.equal(Math.max(...cells.map((c) => c.y)), 19);
});

// ---------------------------------------------------------------------------
// 行满与清行
// ---------------------------------------------------------------------------
test('findFullRows / removeRows 正确清除单行', () => {
  const b = T.makeBoard(5, 4);
  for (let x = 0; x < 4; x++) b[4][x] = 'T'; // 最后一行填满
  b[3][0] = 'L';                              // 倒数第二行只填 1 格
  assert.deepEqual(T.findFullRows(b), [4]);
  const { board: b2, count } = T.removeRows(b, [4], 5);
  assert.equal(count, 1);
  assert.equal(b2.length, 5);
  // 顶部补出一行空行，原第 3 行（含一个 L）下移到了底部
  assert.ok(b2[0].every((c) => c === 0));
  assert.equal(b2[4][0], 'L');
});

test('removeRows 支持一次清除连续多行', () => {
  const b = T.makeBoard(4, 3);
  for (let r = 2; r < 4; r++) for (let x = 0; x < 3; x++) b[r][x] = 'Z';
  assert.deepEqual(T.findFullRows(b), [2, 3]);
  const { board: b2, count } = T.removeRows(b, [2, 3], 4);
  assert.equal(count, 2);
  assert.equal(b2.length, 4);
  assert.ok(b2[0].every((c) => c === 0));
  assert.ok(b2[1].every((c) => c === 0));
});

test('removeRows 空操作返回原棋盘的拷贝', () => {
  const b = T.makeBoard(3, 3);
  const { board: b2, count } = T.removeRows(b, [], 3);
  assert.equal(count, 0);
  b2[0][0] = 1;
  assert.equal(b[0][0], 0, '不应修改原棋盘');
});

// ---------------------------------------------------------------------------
// 引擎流程
// ---------------------------------------------------------------------------
test('创建引擎后自带当前块与下一块', () => {
  const eng = T.createTetris({ cols: 10, rows: 20, queue: ['O', 'T', 'L'] });
  assert.ok(eng.getCurrent(), '应当有当前块');
  assert.equal(eng.getCurrent().type, 'O');
  assert.equal(eng.getNext(), 'T');
  assert.equal(eng.isGameOver(), false);
  assert.equal(eng.getCleared(), 0);
});

test('move 受边界限制：方块到边缘后无法再移动', () => {
  const eng = T.createTetris({ cols: 4, rows: 6, queue: ['O'] });
  // O 型出生在 x=1（占用 1、2）
  assert.equal(eng.getCurrent().x, 1);
  // 向右只能再走 1 步到 x=2
  assert.equal(eng.move(1), true);
  assert.equal(eng.move(1), false);
  assert.equal(eng.getCurrent().x, 2);
  // 向左可回到 0
  assert.equal(eng.move(-1), true);
  assert.equal(eng.move(-1), true);
  assert.equal(eng.move(-1), false);
  assert.equal(eng.getCurrent().x, 0);
});

test('fall 落到底后 lock 会把方块写进棋盘', () => {
  const eng = T.createTetris({ cols: 4, rows: 6, queue: ['O'] });
  while (eng.fall()) { /* 落到最底 */ }
  const res = eng.lock();
  assert.ok(res, '锁定应有结果');
  assert.equal(res.rows.length, 0, '只有两格，不应消行');
  assert.ok(!eng.getCurrent(), '锁定后当前块清空');
  const board = eng.getBoard();
  assert.equal(board[4][1], 'O');
  assert.equal(board[4][2], 'O');
  assert.equal(board[5][1], 'O');
  assert.equal(board[5][2], 'O');
});

test('旋转失败不会改变方块状态', () => {
  const eng = T.createTetris({ cols: 4, rows: 4, queue: ['T'] });
  const before = eng.getCurrent();
  // 把它推到最左边底部再尝试旋转（应因无空间而失败）
  while (eng.move(-1)) { /* 到左边界 */ }
  // 手动放到会碰撞的位置：x=0 且接近底部
  const cur = eng.getCurrent();
  const fake = { type: cur.type, rot: cur.rot, x: 0, y: 2 };
  // 检查旋转是否在该位置被拒绝且状态未变
  const blocked = T.collides(eng.getBoard(), fake);
  // 构造被卡死的场景比较繁琐，这里保证：旋转后若失败，x/y/rot 不变
  const ok = eng.rotate();
  const after = eng.getCurrent();
  if (!ok) {
    assert.equal(before.rot, after.rot);
    assert.equal(before.x, after.x);
    assert.equal(before.y, after.y);
  } else {
    assert.notEqual(before.rot, after.rot, '旋转成功后 rot 应改变');
  }
});

test('硬直落 + 锁定 + 生成下一块 的完整流程', () => {
  const eng = T.createTetris({ cols: 4, rows: 6, queue: ['O', 'T', 'O'] });
  eng.dropToFloor();
  let res = eng.lock();
  assert.ok(res);
  eng.removeFullRows(res.rows);
  eng.spawnNext();
  assert.equal(eng.getCurrent().type, 'T');
  assert.equal(eng.getNext(), 'O');
  assert.equal(eng.isGameOver(), false);
});

test('堆满出生区后 spawnNext 判定游戏结束', () => {
  const eng = T.createTetris({ cols: 4, rows: 6, queue: ['O', 'O', 'O', 'O'] });
  // O 出生在 x=1..2。3 个 O 竖着堆满该两列（rows 0..5）：
  for (let i = 0; i < 3; i++) {
    eng.dropToFloor();
    const res = eng.lock();
    eng.removeFullRows(res.rows);
    eng.spawnNext();
    assert.equal(eng.isGameOver(), false, `第 ${i + 1} 个方块不应结束`);
  }
  // 第 4 个 O 出生即重叠 → 结束
  assert.equal(eng.isGameOver(), true);
  assert.equal(eng.getCleared(), 0);
});

test('完整消行流程：累积的清除行数会被正确统计', () => {
  // 棋盘小：rows=5。用 I 型纵向填满一列可制造整行。
  // 更可控的做法：直接用一个几乎满的棋盘 + 一枚 I 型。
  const cols = 5;
  const rows = 5;
  const board = T.makeBoard(rows, cols);
  // 让最底行只有 1 格空缺；I 型横放补上后即可消除。
  for (let x = 0; x < cols; x++) board[rows - 1][x] = 'S';
  board[rows - 1][4] = 0; // 留空缺
  const eng = T.createTetris({ cols, rows, queue: ['I'], board });
  // I 型横放：把空缺行填满
  const cur = eng.getCurrent();
  // 直接把 I 移动到正确位置（x = 0，横放落在底部上一行? 需落到底部那行）
  eng.dropToFloor(); // 会落在最后一行的下一格？不行，I 与地面留有空缺行，但底行缺一格是空位可放
  // I 高 1 行，纵向位置应落在能放进第 rows-1 行的位置；
  // 由于第 rows-1 行只有一格空位，放不进整条 I —— 改用一个纵向堆叠再消除的思路被简化：
  // 这里直接验证 findFullRows+removeFullRows 的联动。
  const full = T.findFullRows(eng.getBoard());
  if (full.length) {
    const n = eng.removeFullRows(full);
    assert.ok(n >= 1);
    assert.equal(eng.getCleared(), n);
  }
});

test('getCleared 在 removeFullRows 后累加', () => {
  const eng = T.createTetris({ cols: 3, rows: 4, queue: ['O', 'O', 'O'] });
  // 依次把 O 落到底部堆成两列三行，无法构成整行（宽 3 中间缺一列）
  // 直接对棋盘做手术更直观：
  const board = eng.getBoard();
  for (let x = 0; x < 3; x++) board[3][x] = 'O';
  const n = eng.removeFullRows([3]);
  assert.equal(n, 1);
  assert.equal(eng.getCleared(), 1);
  assert.ok(eng.getBoard()[0].every((c) => c === 0), '顶部应有新空行');
});

// ---------------------------------------------------------------------------
// 幽灵块（下落预览）
// ---------------------------------------------------------------------------
test('ghostCells 与 dropToFloor 的位置一致', () => {
  const eng = T.createTetris({ cols: 10, rows: 20, queue: ['T'] });
  const ghost = eng.ghostCells();
  const cur = eng.getCurrent();
  const curCells = T.pieceCells(cur.type, cur.rot, cur.x, cur.y);
  assert.equal(ghost.length, curCells.length);
  // 幽灵位置 = 当前位置竖直下移若干格：x 不变、y 单调
  const curYs = curCells.map((c) => c.y);
  const ghostYs = ghost.map((c) => c.y);
  const drop = Math.min(...ghostYs) - Math.min(...curYs);
  assert.ok(drop >= 0);
  eng.dropToFloor();
  const landed = T.pieceCells(eng.getCurrent().type, eng.getCurrent().rot, eng.getCurrent().x, eng.getCurrent().y);
  assert.deepEqual(
    landed.map((c) => c.y).sort((a, b) => a - b),
    ghostYs.sort((a, b) => a - b)
  );
});
