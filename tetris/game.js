/**
 * game.js — 俄罗斯方块游戏逻辑核心（纯逻辑，不依赖任何 DOM / 浏览器 API）
 *
 * 可在两种环境下运行：
 *   1. 浏览器：<script src="game.js"></script>  之后通过全局变量 Tetris 使用
 *   2. Node：  const Tetris = require('./game')
 *
 * 设计约定：
 *   - 网格 board 为二维数组，rows 行 × cols 列；0 表示空，否则存放方块字母(类型)。
 *   - 方块 piece = { type, rot, x, y }，其中 x/y 为该旋转状态下矩阵左上角的位置，
 *     rot 为 SHAPES[type] 旋转矩阵数组的下标。
 *   - 为了界面做消行动画，锁定(lock)与清行(removeRows)分两步：
 *       引擎先 lock（合并且找出满行，但不清除），界面播放动画后再调用 removeRows。
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.Tetris = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  // ---------------------------------------------------------------------------
  // 方块形状定义：每个类型的值是“旋转状态”数组，每个状态是一个 0/1 矩阵
  // ---------------------------------------------------------------------------
  var SHAPES = {
    I: [
      [
        [0, 0, 0, 0],
        [1, 1, 1, 1],
        [0, 0, 0, 0],
        [0, 0, 0, 0]
      ],
      [
        [0, 0, 1, 0],
        [0, 0, 1, 0],
        [0, 0, 1, 0],
        [0, 0, 1, 0]
      ],
      [
        [0, 0, 0, 0],
        [0, 0, 0, 0],
        [1, 1, 1, 1],
        [0, 0, 0, 0]
      ],
      [
        [0, 1, 0, 0],
        [0, 1, 0, 0],
        [0, 1, 0, 0],
        [0, 1, 0, 0]
      ]
    ],
    O: [
      [
        [1, 1],
        [1, 1]
      ]
    ],
    J: [
      [
        [1, 0, 0],
        [1, 1, 1],
        [0, 0, 0]
      ],
      [
        [0, 1, 1],
        [0, 1, 0],
        [0, 1, 0]
      ],
      [
        [0, 0, 0],
        [1, 1, 1],
        [0, 0, 1]
      ],
      [
        [0, 1, 0],
        [0, 1, 0],
        [1, 1, 0]
      ]
    ],
    L: [
      [
        [0, 0, 1],
        [1, 1, 1],
        [0, 0, 0]
      ],
      [
        [0, 1, 0],
        [0, 1, 0],
        [0, 1, 1]
      ],
      [
        [0, 0, 0],
        [1, 1, 1],
        [1, 0, 0]
      ],
      [
        [1, 1, 0],
        [0, 1, 0],
        [0, 1, 0]
      ]
    ],
    S: [
      [
        [0, 1, 1],
        [1, 1, 0],
        [0, 0, 0]
      ],
      [
        [0, 1, 0],
        [0, 1, 1],
        [0, 0, 1]
      ]
    ],
    Z: [
      [
        [1, 1, 0],
        [0, 1, 1],
        [0, 0, 0]
      ],
      [
        [0, 0, 1],
        [0, 1, 1],
        [0, 1, 0]
      ]
    ],
    T: [
      [
        [0, 1, 0],
        [1, 1, 1],
        [0, 0, 0]
      ],
      [
        [0, 1, 0],
        [0, 1, 1],
        [0, 1, 0]
      ],
      [
        [0, 0, 0],
        [1, 1, 1],
        [0, 1, 0]
      ],
      [
        [0, 1, 0],
        [1, 1, 0],
        [0, 1, 0]
      ]
    ]
  };

  var TYPES = ['I', 'O', 'T', 'S', 'Z', 'J', 'L'];

  // ---------------------------------------------------------------------------
  // 纯工具函数
  // ---------------------------------------------------------------------------
  function makeRow(cols) {
    var r = [];
    for (var i = 0; i < cols; i++) r.push(0);
    return r;
  }

  function makeBoard(rows, cols) {
    var b = [];
    for (var i = 0; i < rows; i++) b.push(makeRow(cols));
    return b;
  }

  function copyBoard(board) {
    return board.map(function (row) { return row.slice(); });
  }

  function shuffle(arr, rng) {
    for (var i = arr.length - 1; i > 0; i--) {
      var j = Math.floor(rng() * (i + 1));
      var t = arr[i]; arr[i] = arr[j]; arr[j] = t;
    }
    return arr;
  }

  /** 将一个 0/1 旋转矩阵转换为 [{x,y}, ...] 坐标列表 */
  function matrixCells(matrix) {
    var out = [];
    for (var r = 0; r < matrix.length; r++) {
      for (var c = 0; c < matrix[r].length; c++) {
        if (matrix[r][c]) out.push({ x: c, y: r });
      }
    }
    return out;
  }

  /** 计算某类型在某旋转下、放在 (x, y) 处的绝对格子坐标 */
  function pieceCells(type, rot, x, y) {
    var m = SHAPES[type][rot];
    var cells = [];
    for (var r = 0; r < m.length; r++) {
      for (var c = 0; c < m[r].length; c++) {
        if (m[r][c]) cells.push({ x: x + c, y: y + r });
      }
    }
    return cells;
  }

  /**
   * 碰撞检测：是否与边界或已堆积的格子重叠。
   * 越界（含上方 y<0、下方 y>=rows、左右越界）一律视为碰撞。
   */
  function collides(board, piece) {
    if (!piece) return true;
    var rows = board.length;
    var cols = board[0].length;
    var cells = pieceCells(piece.type, piece.rot, piece.x, piece.y);
    for (var i = 0; i < cells.length; i++) {
      var x = cells[i].x;
      var y = cells[i].y;
      if (x < 0 || x >= cols || y < 0 || y >= rows) return true;
      if (board[y][x] !== 0) return true;
    }
    return false;
  }

  /** 方块在当前位置还能向下落多少格 */
  function dropDistance(board, piece) {
    var d = 0;
    for (;;) {
      var probe = { type: piece.type, rot: piece.rot, x: piece.x, y: piece.y + d + 1 };
      if (collides(board, probe)) return d;
      d++;
    }
  }

  /** 找出所有整行已满的行号（升序） */
  function findFullRows(board) {
    var out = [];
    for (var r = 0; r < board.length; r++) {
      var full = true;
      for (var c = 0; c < board[r].length; c++) {
        if (board[r][c] === 0) { full = false; break; }
      }
      if (full) out.push(r);
    }
    return out;
  }

  /**
   * 删除指定行，并在顶部补空行。
   * @returns {{ board: Array, count: number }}
   */
  function removeRows(board, rowsToRemove, rowCount) {
    if (!rowsToRemove || rowsToRemove.length === 0) {
      return { board: copyBoard(board), count: 0 };
    }
    var set = {};
    for (var i = 0; i < rowsToRemove.length; i++) set[rowsToRemove[i]] = true;
    var cols = board.length ? board[0].length : 0;
    var kept = [];
    for (var r = 0; r < board.length; r++) {
      if (!set[r]) kept.push(board[r].slice());
    }
    while (kept.length < rowCount) kept.unshift(makeRow(cols));
    return { board: kept, count: rowsToRemove.length };
  }

  /** 计算某类型在出生位置的 piece */
  function spawnPiece(type, cols) {
    var m = SHAPES[type][0];
    var minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (var r = 0; r < m.length; r++) {
      for (var c = 0; c < m[r].length; c++) {
        if (m[r][c]) {
          if (c < minX) minX = c;
          if (c > maxX) maxX = c;
          if (r < minY) minY = r;
          if (r > maxY) maxY = r;
        }
      }
    }
    var width = maxX - minX + 1;
    var ox = Math.floor((cols - width) / 2) - minX;
    var oy = -minY; // 让方块的最高格贴住顶部（I 型会略微“从顶部进入”）
    return { type: type, rot: 0, x: ox, y: oy };
  }

  // ---------------------------------------------------------------------------
  // 引擎：封装棋盘、当前块、下一块、7-bag 随机等
  // ---------------------------------------------------------------------------
  function createTetris(options) {
    options = options || {};
    var ROWS = options.rows || 20;
    var COLS = options.cols || 10;
    var rng = options.rng || Math.random;

    var fixedQueue = options.queue ? options.queue.slice() : null;
    var deck = fixedQueue ? fixedQueue.slice() : [];

    var board = options.board ? copyBoard(options.board) : makeBoard(ROWS, COLS);
    var current = null;
    var next = null;
    var over = false;
    var cleared = 0;

    function takeFromBag() {
      if (deck.length) return deck.shift();
      if (fixedQueue) {
        deck = fixedQueue.slice(); // 测试/循环用：固定序列耗尽后自动再来一遍
        return deck.shift();
      }
      deck = TYPES.slice();
      shuffle(deck, rng);
      return deck.shift();
    }

    /** 生成下一块。若出生即碰撞 → 游戏结束 */
    function spawnNext() {
      if (current) return current;
      if (!next) next = takeFromBag();
      var type = next;
      next = takeFromBag();
      current = spawnPiece(type, COLS);
      if (!over && collides(board, current)) over = true;
      return current;
    }

    function move(dir) {
      if (!current || over) return false;
      var probe = { type: current.type, rot: current.rot, x: current.x + dir, y: current.y };
      if (collides(board, probe)) return false;
      current.x += dir;
      return true;
    }

    function rotate() {
      if (!current || over) return false;
      var rotCount = SHAPES[current.type].length;
      if (rotCount < 2) return true; // O 块
      var nr = (current.rot + 1) % rotCount;
      var kicks = [
        [0, 0], [-1, 0], [1, 0],
        [0, -1], [0, 1],
        [-2, 0], [2, 0]
      ];
      for (var i = 0; i < kicks.length; i++) {
        var probe = {
          type: current.type,
          rot: nr,
          x: current.x + kicks[i][0],
          y: current.y + kicks[i][1]
        };
        if (!collides(board, probe)) {
          current = probe;
          return true;
        }
      }
      return false;
    }

    /** 自然下落一步；返回是否下落成功 */
    function fall() {
      if (!current || over) return false;
      var probe = { type: current.type, rot: current.rot, x: current.x, y: current.y + 1 };
      if (collides(board, probe)) return false;
      current.y += 1;
      return true;
    }

    /** 直落：瞬间落到底 */
    function dropToFloor() {
      if (!current || over) return false;
      current.y += dropDistance(board, current);
      return true;
    }

    /**
     * 将当前块合并进棋盘，并找出满行（不清除、不生成下一块）。
     * 界面完成消行动画后应调用 removeRows + spawnNext。
     * @returns {{cells:Array, rows:Array} | null}
     */
    function lock() {
      if (!current || over) return null;
      var cells = pieceCells(current.type, current.rot, current.x, current.y);
      for (var i = 0; i < cells.length; i++) {
        var x = cells[i].x;
        var y = cells[i].y;
        if (y >= 0 && y < ROWS && x >= 0 && x < COLS) board[y][x] = current.type;
      }
      current = null;
      return { cells: cells, rows: findFullRows(board) };
    }

    /** 动画结束后真正删除满行 */
    function removeFullRows(rowsToRemove) {
      var result = removeRows(board, rowsToRemove || [], ROWS);
      board = result.board;
      cleared += result.count;
      return result.count;
    }

    function ghostCells() {
      if (!current) return [];
      var y = current.y + dropDistance(board, current);
      return pieceCells(current.type, current.rot, current.x, y);
    }

    // 初始状态：先准备当前块与下一块
    spawnNext();

    return {
      // ---- 配置 / 状态访问 ----
      getRows: function () { return ROWS; },
      getCols: function () { return COLS; },
      getBoard: function () { return board; },
      getCurrent: function () { return current; },
      getNext: function () { return next; },
      isGameOver: function () { return over; },
      getCleared: function () { return cleared; },
      // ---- 操作 ----
      move: move,
      rotate: rotate,
      fall: fall,
      dropToFloor: dropToFloor,
      lock: lock,
      removeFullRows: removeFullRows,
      spawnNext: spawnNext,
      ghostCells: ghostCells
    };
  }

  // ---------------------------------------------------------------------------
  return {
    SHAPES: SHAPES,
    TYPES: TYPES,
    makeRow: makeRow,
    makeBoard: makeBoard,
    copyBoard: copyBoard,
    matrixCells: matrixCells,
    pieceCells: pieceCells,
    collides: collides,
    dropDistance: dropDistance,
    findFullRows: findFullRows,
    removeRows: removeRows,
    spawnPiece: spawnPiece,
    createTetris: createTetris
  };
});
