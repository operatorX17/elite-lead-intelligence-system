"use client";

import type { DataUIPart } from "ai";
import type React from "react";
import { createContext, useContext, useMemo, useState } from "react";
import type { CustomUIDataTypes, ZRAIActivityEvent } from "@/lib/types";

type DataStreamContextValue = {
  dataStream: DataUIPart<CustomUIDataTypes>[];
  setDataStream: React.Dispatch<
    React.SetStateAction<DataUIPart<CustomUIDataTypes>[]>
  >;
  zraiActivityEvents: ZRAIActivityEvent[];
  setZraiActivityEvents: React.Dispatch<
    React.SetStateAction<ZRAIActivityEvent[]>
  >;
};

const DataStreamContext = createContext<DataStreamContextValue | null>(null);

export function DataStreamProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [dataStream, setDataStream] = useState<DataUIPart<CustomUIDataTypes>[]>(
    []
  );
  const [zraiActivityEvents, setZraiActivityEvents] = useState<
    ZRAIActivityEvent[]
  >([]);

  const value = useMemo(
    () => ({
      dataStream,
      setDataStream,
      zraiActivityEvents,
      setZraiActivityEvents,
    }),
    [dataStream, zraiActivityEvents]
  );

  return (
    <DataStreamContext.Provider value={value}>
      {children}
    </DataStreamContext.Provider>
  );
}

export function useDataStream() {
  const context = useContext(DataStreamContext);
  if (!context) {
    throw new Error("useDataStream must be used within a DataStreamProvider");
  }
  return context;
}
