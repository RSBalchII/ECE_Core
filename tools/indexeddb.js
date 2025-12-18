let db = null;
let cozoDbStore = null;
let writeCounter = 0;
let writeCallback = null;

let cmdFlag = false;

export function setWriteCounter(count) {
  writeCounter = count;
}

function storeRequestToPromise(req) {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result);
    req.onerror = (e) => reject(e.error);
  });
}

async function openDatabase(dbName, storeName) {
  cozoDbStore = storeName;

  return new Promise((resolve, reject) => {
    const request = indexedDB.open(dbName, 1);
    request.onupgradeneeded = function (event) {
      const db = event.target.result;
      if (!db.objectStoreNames.contains(storeName)) {
        db.createObjectStore(storeName);
      }
    };

    request.onsuccess = function (event) {
      db = event.target.result;
      resolve(db);
    };
    request.onerror = function (event) {
      reject(event.error);
    };
  });
}

async function readStore() {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(cozoDbStore, "readonly");
    const store = transaction.objectStore(cozoDbStore);

    const itemsPromise = storeRequestToPromise(store.getAll());
    const keysPromise = storeRequestToPromise(store.getAllKeys());

    Promise.all([keysPromise, itemsPromise])
      .then((results) => {
        const keys = results[0].map((item) => new Uint8Array(item));
        const items = results[1];
        resolve([keys, items]);
      })
      .catch(reject);
  });
}

export async function flushPendingWrites(timeoutDuration = 60000) {
  let timeout = null;

  // allow only one command runnig at a time
  if (cmdFlag) {
    await new Promise((resolve, reject) => {
      const interval = setInterval(() => {
        if (!cmdFlag) {
          clearInterval(interval);
          resolve();
        }
      }, 10);
    });
  }

  cmdFlag = true;

  const waitPromise = new Promise((resolve, reject) => {
    const interval = setInterval(() => {
      if (writeCounter <= 0) {
        if (timeout) {
          clearTimeout(timeout);
        }
        clearInterval(interval);
        resolve();
      }
    }, 10);
  });

  const timeoutPromise = new Promise((_, reject) => {
    timeout = setTimeout(() => {
      reject(new Error("waitForPendingWrites timed out!"));
    }, timeoutDuration);
  });

  // wait until all pending writes are done
  return Promise.race([waitPromise, timeoutPromise]).finally(() => {
    cmdFlag = false;
  });
}

export async function loadAllFromIndexedDb(dbName, storeName, onWriteCallback) {
  writeCallback = onWriteCallback;
  await openDatabase(dbName, storeName);
  return await readStore();
}

export async function writeToIndexedDb(key, value) {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(cozoDbStore, "readwrite");
    const store = transaction.objectStore(cozoDbStore);
    const request = value ? store.put(value, key) : store.delete(key);
    return storeRequestToPromise(request)
      .then(resolve)
      .catch(reject)
      .finally(() => {
        writeCounter--;
        writeCallback && writeCallback(writeCounter);
      });
  });
}

export function closeDatabase() {
  if (db) {
    db.close();
    db = null;
  }
}

export async function clearIndexedDbStore(dbName, storeName) {
  // Ensure we open a connection first if one isn't open
  if (!db) {
    await openDatabase(dbName, storeName);
  }
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(storeName, "readwrite");
    const store = transaction.objectStore(storeName);
    const request = store.clear();

    request.onsuccess = () => resolve();
    request.onerror = (e) => reject(e.target.error);
  });
}
