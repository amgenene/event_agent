import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import { SearchPageClient } from "./SearchPageClient";

export default async function SearchPage() {
  const { userId } = await auth();
  if (!userId) redirect("/sign-in");

  return <SearchPageClient />;
}
