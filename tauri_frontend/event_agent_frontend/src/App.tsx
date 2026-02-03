import "./App.css";
import MinimalRecorder from "./MinimalRecorder";

function App() {
  return (
    <main className="container" style={{
      background: "#0a0a0f",
      minHeight: "100vh",
      padding: 0
    }}>
      <MinimalRecorder />
    </main>
  );
}

export default App;
