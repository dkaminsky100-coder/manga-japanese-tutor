import { BrowserRouter, Route, Routes } from 'react-router-dom'
import Library from './pages/Library'
import Reader from './pages/Reader'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Library />} />
        <Route path="/read/:chapterId" element={<Reader />} />
      </Routes>
    </BrowserRouter>
  )
}
