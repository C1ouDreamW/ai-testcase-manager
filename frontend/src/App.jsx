import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import AppLayout from './layouts/AppLayout';
import Evaluation from './pages/Evaluation';
import GenerateFlow from './pages/GenerateFlow';
import Knowledge from './pages/Knowledge';
import ProjectDetail from './pages/ProjectDetail';
import ProjectList from './pages/ProjectList';
import Settings from './pages/Settings';
import TestCaseLibrary from './pages/TestCaseLibrary';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AppLayout />}>
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
