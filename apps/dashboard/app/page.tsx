import { redirect } from "next/navigation";

export default function Home() {
  // Redirect to channels page as the main entry point
  redirect("/channels");
}
