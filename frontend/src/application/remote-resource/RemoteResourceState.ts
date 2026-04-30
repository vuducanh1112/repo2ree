type RemoteResourceState<T> =
  | { status: "idle" }
  | { status: "loading"; data?: T }
  | { status: "success"; data: T }
  | { status: "error"; error: Error; data?: T };

interface RemoteQuerySnapshot<T> {
  data?: T;
  error: Error | null;
  isPending: boolean;
  isFetching: boolean;
}

export function toRemoteResourceState<T>(snapshot: RemoteQuerySnapshot<T>): RemoteResourceState<T> {
  if (snapshot.error) {
    return {
      status: "error",
      error: snapshot.error,
      data: snapshot.data,
    };
  }

  if (snapshot.isPending) {
    return snapshot.data == null ? { status: "idle" } : { status: "loading", data: snapshot.data };
  }

  if (snapshot.isFetching) {
    return { status: "loading", data: snapshot.data };
  }

  if (snapshot.data == null) {
    return { status: "idle" };
  }

  return {
    status: "success",
    data: snapshot.data,
  };
}
