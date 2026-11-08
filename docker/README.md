# Docker 一键启动说明

这个项目原来把基础设施分散在几个地方（`开发说明` 里写的那种）：

- Milvus + etcd + MinIO 用 `D:\milvus` 下的另一套 compose 起
- `mongo`、`attu` 是各一条 `docker run`
- 另外还有个 `cgr.dev/chainguard/minio`（已 Exited，不再需要）

现在统一到项目根目录的 `docker-compose.yml`，项目名 `gewu`（格物致知），Docker Desktop 的 **Containers** 页面里会显示成一个 `gewu` 分组，可以整组启动/停止/重启。

> **当前状态（2026-11-08 已迁移完成）**：旧容器已删除，`gewu` 项目 5 个容器全部运行中，日常只需要 `docker-start.bat` / `docker-stop.bat`。第 2 节的迁移步骤保留作为记录，不用再跑。
>
> 迁移后实测（数据都在）：
>
> - Milvus：`kb_item_names` 3 行、`kb_chunks` 69 行，`/healthz` 返回 OK
> - MongoDB：`kb002.chat_message` 10 条
> - MinIO：`a-bucket`、`knowledge-base-files` 两个桶
>
> 并且完整跑过一轮 `docker-stop.bat` → `docker-start.bat` 往返，重启后上面这些数据仍然一致。
>
> 旧 mongo 匿名卷 `5bbe7313…`（205M）暂时留着当备份，确认一段时间没问题后再 `docker volume rm 5bbe73131437b11bbdfcb6c6b37a4122c4bc4edd4b9711cfa0286907ca63c47b` 回收。

---

## 1. 一键启动 / 停止

| 操作 | 方式 |
| --- | --- |
| 启动 | 双击根目录 `docker-start.bat`，或 `docker compose up -d` |
| 停止（保留数据） | 双击 `docker-stop.bat`，或 `docker compose down` |
| 查看状态 | `docker compose ps` |
| 看某个服务日志 | `docker compose logs -f standalone` |

首次启动 Milvus 大概要 1–2 分钟（要先等 etcd、MinIO 变健康），`docker compose ps` 里 `milvus-standalone` 显示 `healthy` 就绪了。

> 两个 `.bat` 的提示信息是英文的：批处理里的中文在 cmd 下会受代码页影响变成乱码，所以中文说明统一放在这份文档里。

**只包含基础设施容器**，两个 Python 服务仍然在宿主机上跑：

```powershell
uvicorn app.import_process.api.file_import_service:app --host 0.0.0.0 --port 8000 --reload
uvicorn app.query_process.api.query_server:app --host 0.0.0.0 --port 8001 --reload
```

---

## 2. 首次迁移（已于 2026-11-08 执行完毕，以下保留作为记录）

> 已经执行过了，不用再跑。换新机器 / 重装 Docker 时才需要参考。

现在跑着的 5 个容器是 `docker run` / 另一个 compose 建的，**名字和新的 compose 完全一样**，所以直接 `docker compose up` 会报 `container name is already in use`。按下面三步走一次：

```powershell
# ① 先把老 mongo 的数据搬进 compose 用的具名卷（会自动停掉老 mongo 容器）
#    老 mongo 是 `docker run ... mongo` 起的，没指定卷，数据在一个哈希名匿名卷里，
#    不迁移的话新库是空的（老卷不会删，只是不再被使用）
.\docker\migrate-mongo-data.ps1

# ② 删掉旧的 5 个容器；注意不要加 -v，加了会连卷一起删
docker rm -f mongo attu milvus-standalone milvus-etcd milvus-minio

# ③ 一键启动
.\docker-start.bat
```

> Milvus / etcd / MinIO 的数据**不需要迁移**：compose 里直接绑定了原来的 `D:\milvus\volumes\{milvus,etcd,minio}`，所以向量库原样还在。
> 也**别删 `D:\milvus` 这个目录**，除非你按第 5 节把数据搬进了项目里。
> Attu 的卷也沿用了老的 `attu-data`，登录配置还在。

迁移后可以顺手清掉一堆早就 Exited 的残留容器（Dify 那一批等），让 Docker Desktop 清爽些：

```powershell
docker container prune     # 只删已停止的容器，不动镜像和卷
```

---

## 3. 端口对照（和 `.env` 完全对得上，不用改代码）

| 服务 | 容器名 | 宿主机端口 | 对应 `.env` |
| --- | --- | --- | --- |
| Milvus gRPC | `milvus-standalone` | `19530` | `MILVUS_URL=http://127.0.0.1:19530` |
| Milvus 健康检查 | `milvus-standalone` | `9091` | 浏览器打开 `http://127.0.0.1:9091/healthz` |
| MinIO 数据口 | `milvus-minio` | `9002` → 容器 9000 | `MINIO_ENDPOINT=127.0.0.1:9002` |
| MinIO 控制台 | `milvus-minio` | `9003` → 容器 9001 | <http://127.0.0.1:9003>（minioadmin / minioadmin） |
| Attu | `attu` | `3000` | <http://127.0.0.1:3000> |
| MongoDB | `mongo` | `27017` | `MONGO_URL=mongodb://127.0.0.1:27017` |
| etcd | `milvus-etcd` | 不对外暴露 | Milvus 内部用 |

MinIO 的账号密码直接取自 `.env` 里的 `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY`，两处不会打架。

---

## 4. 数据放在哪

| 数据 | 位置 | 说明 |
| --- | --- | --- |
| Milvus 向量库 | `D:\milvus\volumes\milvus` | 绑定目录，沿用原位置 |
| etcd | `D:\milvus\volumes\etcd` | 绑定目录，沿用原位置 |
| MinIO 对象文件 | `D:\milvus\volumes\minio` | 绑定目录，沿用原位置 |
| MongoDB | 具名卷 `gewu-mongo-data` | 放在 Docker 里而不是 Windows 目录，避免 WSL2 下的 MongoDB 文件锁问题 |
| Attu 配置 | 具名卷 `attu-data` | 沿用原有卷 |

备份 Milvus 就是停掉容器后复制 `D:\milvus\volumes`；备份 MongoDB：

```powershell
docker run --rm -v gewu-mongo-data:/data -v ${PWD}:/backup mongo `
  sh -c "mongodump --uri mongodb://localhost:27017 --archive=/backup/mongo.archive --gzip"
```

---

## 5. 想把数据都搬进项目里（可选）

默认沿用 `D:\milvus\volumes`，是为了零风险、不动现有数据。如果希望整个项目的状态都收在 `D:\workspace\RAGData` 下：

```powershell
docker compose down
mkdir docker\volumes -Force
robocopy D:\milvus\volumes\etcd   docker\volumes\etcd   /E
robocopy D:\milvus\volumes\minio  docker\volumes\minio  /E
robocopy D:\milvus\volumes\milvus docker\volumes\milvus /E
```

然后在项目根目录的 `.env` 里加三行（compose 会自动读项目根的 `.env`；这几行对 Python 代码没有副作用）：

```dotenv
MILVUS_ETCD_DIR=./docker/volumes/etcd
MILVUS_MINIO_DIR=./docker/volumes/minio
MILVUS_DATA_DIR=./docker/volumes/milvus
```

确认启动正常、数据都在之后，`D:\milvus` 就可以退休了。

---

## 6. 常见问题

**报 `container name "/mongo" is already in use`**
旧容器没清干净。`docker rm -f mongo attu milvus-standalone milvus-etcd milvus-minio` 再启动（别加 `-v`）。

**报端口被占用**（`bind: address already in use`）
```powershell
netstat -ano | findstr :19530     # 把 19530 换成报错的端口，再用 taskkill /PID <pid> /F 处理
```

**`milvus-standalone` 一直 `unhealthy` / 重启**
```powershell
docker compose logs --tail 100 standalone
```
常见原因：etcd 或 MinIO 没起来、`D:\milvus\volumes\milvus` 被别的进程占用、磁盘空间不足。

**Attu 打开后连不上 Milvus**
Attu 里配置的地址是 `milvus-standalone:19530`（compose 网络内）。宿主机上想手动连的话填 `127.0.0.1:19530`。

**`docker compose up` 时提示 `volume "attu-data" already exists but was not created by Docker Compose`**
可以忽略。这是 compose 在复用你原有的两个具名卷（`attu-data`、`gewu-mongo-data`），不影响使用。

**桌面里还是看着乱**
`docker compose` 建的容器只要项目名一致就会归到一个分组；把旧的散容器删掉、再 `docker container prune` 清掉 Exited 的，列表就干净了。

**改了 compose 想生效**
```powershell
docker compose up -d --force-recreate
```
