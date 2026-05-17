# Welcome to MkDocs

For full documentation visit [mkdocs.org](https://www.mkdocs.org).

## Commands

- `mkdocs new [dir-name]` - Create a new project.
- `mkdocs serve` - Start the live-reloading docs server.
- `mkdocs build` - Build the documentation site.
- `mkdocs -h` - Print help message and exit.

## Project layout

    mkdocs.yml    # The configuration file.
    docs/
        index.md  # The documentation homepage.
        ...       # Other markdown pages, images and other files.

## Mermaid 図

スニペット: `mermaid` または `フロー`

### フローチャート

````markdown
```mermaid
graph TD
    A[開始] --> B{条件分岐}
    B -->|Yes| C[処理A]
    B -->|No| D[処理B]
    C --> E[終了]
    D --> E
```
````

```mermaid
graph TD
    A[開始] --> B{条件分岐}
    B -->|Yes| C[処理A]
    B -->|No| D[処理B]
    C --> E[終了]
    D --> E
```

### シーケンス図

スニペット: `sequence` または `シーケンス`

````markdown
```mermaid
sequenceDiagram
    participant U as ユーザー
    participant S as サーバー
    participant D as データベース

    U->>+S: リクエスト
    S->>+D: クエリ
    D-->>-S: 結果
    S-->>-U: レスポンス
```
````

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant S as サーバー
    participant D as データベース

    U->>+S: リクエスト
    S->>+D: クエリ
    D-->>-S: 結果
    S-->>-U: レスポンス
```

### ガントチャート

スニペット: `gantt` または `ガント`

````markdown
```mermaid
gantt
    title プロジェクトスケジュール
    dateFormat YYYY-MM-DD
    section フェーズ1
    設計       :a1, 2024-01-01, 14d
    開発       :a2, after a1, 21d
    section フェーズ2
    テスト     :a3, after a2, 14d
    リリース   :milestone, after a3, 0d
```
````

```mermaid
gantt
    title プロジェクトスケジュール
    dateFormat YYYY-MM-DD
    section フェーズ1
    設計       :a1, 2024-01-01, 14d
    開発       :a2, after a1, 21d
    section フェーズ2
    テスト     :a3, after a2, 14d
    リリース   :milestone, after a3, 0d
```

```python
print(Hello World.)
```
