import {Composition} from 'remotion';
import {StepGraphic, type StepKey} from './Composition';

const steps: Array<{id: string; step: StepKey}> = [
  {id: 'Step01Connect', step: 'connect'},
  {id: 'Step02Choose', step: 'choose'},
  {id: 'Step03Save', step: 'save'},
  {id: 'Step04Review', step: 'review'},
  {id: 'Step05Draw', step: 'draw'},
];

export const RemotionRoot: React.FC = () => (
  <>
    {steps.map(({id, step}) => (
      <Composition
        key={id}
        id={id}
        component={StepGraphic}
        durationInFrames={90}
        fps={30}
        width={1600}
        height={900}
        defaultProps={{step}}
      />
    ))}
  </>
);
