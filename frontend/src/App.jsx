import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import AppLayout from './layouts/AppLayout';
import Evaluation from './pages/Evaluation';
import GenerateFlow from './pages/GenerateFlow';
import Knowledge from './pages/Knowledge';
import Login from './pages/Login';
import ProjectDetail from './pages/ProjectDetail';
import ProjectList from './pages/ProjectList';
import Register from './pages/Register';
import Settings from './pages/Settings';
import TestCaseLibrary from './pages/TestCaseLibrary';
import { getAuth } from './services/api';

function RequireAuth({ children }) {
  const location = useLocation();
  if (!getAuth()?.token) {
    return <Navigate to="/login" state={{ from: location.pathname + location.search }} replace />;
  }
  return children;
}

export default function App() {
  const baseUrl = import.meta.env.BASE_URL || '/';
  const basename = baseUrl === '/' ? undefined : baseUrl.replace(/\/$/, '');

  return (
    <BrowserRouter basename={basename}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/" element={<RequireAuth><AppLayout /></RequireAuth>}>
          <Route index element={<ProjectList />} />
          <Route path="settings" element={<Settings />} />
          <Route path="testcases" element={<TestCaseLibrary />} />
          <Route path="knowledge" element={<Knowledge />} />
          <Route path="evaluation" element={<Evaluation />} />
          <Route path="projects/:projectId" element={<ProjectDetail />} />
          <Route path="projects/:projectId/generate" element={<GenerateFlow />} />
          <Route path="projects/:projectId/testcases" element={<Navigate to="/testcases" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
